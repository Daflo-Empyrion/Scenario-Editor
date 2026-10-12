#nullable enable
// Empyrion Scenario Editor
// Copyright (C) 2026  Daflo
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.
//
// Verificateur de scenario au moteur du JEU :
//   yamlcheck yaml <dossier scenario> [autre dossier...]
//     parse chaque *.yaml avec le YamlDotNet reellement embarque dans
//     Empyrion (YamlAssembly.dll, referencee a la compilation) — reproduit
//     les erreurs exactes du jeu (pyyaml donne des faux positifs).
//   yamlcheck ecf <dossier scenario> [autre dossier...]
//     valide la structure des *.ecf selon la grammaire du format
//     (en-tetes { Nom, Parent, proprietes Cle: Valeur, enfants inline,
//     commentaires # et / * * /, sections CDATA) — le parseur natif du jeu
//     (Eleon.EcfFile dans Assembly-CSharp) n'est pas invocable hors du
//     moteur Unity (statics dejeunes) ; ce validateur en reproduit les
//     regles structurelles, calibre a 0 faux positif sur les corpus de
//     scenarios qui chargent en jeu.
// Protocole stdout (TSV, une ligne par element) :
//   BROKEN\t<chemin relatif>\t<ligne>\t<colonne>\t<message>
//   SUMMARY\t<scannes>\t<casses>\t<ignores>
// Code retour 0 (resultat dans stdout), 2 si dossier absent ou mode inconnu.

using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;
using YamlDotNet.Serialization;

if (args.Length < 2)
{
    Console.Error.WriteLine("usage: yamlcheck yaml|ecf <dossier scenario> [autre dossier...]");
    return 2;
}

var mode = args[0];
var roots = args.Skip(1).ToArray();
if (mode != "yaml" && mode != "ecf")
{
    Console.Error.WriteLine($"mode inconnu : {mode} (yaml|ecf)");
    return 2;
}

Console.OutputEncoding = Encoding.UTF8;
int scanned = 0, broken = 0, ignored = 0;

foreach (var root in roots)
{
    if (!Directory.Exists(root))
    {
        Console.WriteLine($"FATAL\tDossier introuvable : {root}");
        return 2;
    }
    var pattern = mode == "yaml" ? "*.yaml" : "*.ecf";
    foreach (var file in Directory.EnumerateFiles(root, pattern, SearchOption.AllDirectories))
    {
        // fichiers '+' (+playfield_static.yaml, +backup*.ecf...) : sauvegardes
        // d'auteur que le jeu ignore (preuve : Starter_Akua_V2 en porte un et charge)
        if (Path.GetFileName(file).StartsWith('+')) { ignored++; continue; }
        scanned++;
        var rel = Path.GetRelativePath(root, file);
        string? error = mode == "yaml" ? CheckYaml(file) : CheckEcf(file);
        if (error != null)
        {
            broken++;
            var nl = error.IndexOf('\n');
            string firstLine = nl >= 0 ? error[..nl] : error;
            var m = Regex.Match(firstLine, "^ligne (\\d+)(?:, col (\\d+))? : (.*)$");
            if (m.Success)
            {
                var msg = m.Groups[3].Value.Replace('\t', ' ').Replace('\r', ' ').Replace('\n', ' ');
                Console.WriteLine($"BROKEN\t{rel}\t{m.Groups[1].Value}\t{(m.Groups[2].Success ? m.Groups[2].Value : "0")}\t{msg}");
            }
            else
            {
                var msg = firstLine.Replace('\t', ' ').Replace('\r', ' ').Replace('\n', ' ');
                Console.WriteLine($"BROKEN\t{rel}\t0\t0\t{msg}");
            }
        }
    }
}

Console.WriteLine($"SUMMARY\t{scanned}\t{broken}\t{ignored}");
return 0;

// ----------------------------------------------------------------- YAML

string? CheckYaml(string path)
{
    try
    {
        using var reader = new StreamReader(path);
        new Deserializer().Deserialize(reader);
        return null;
    }
    catch (YamlDotNet.Core.YamlException ex)
    {
        return $"ligne {ex.Start.Line}, col {ex.Start.Column} : {ex.Message}";
    }
    catch (Exception ex)
    {
        return $"ligne 0, col 0 : {ex.Message}";
    }
}

// ------------------------------------------------------------------ ECF

// Valide la structure d'un .ecf ; retourne null si sain, sinon un message
// commence par « ligne N : ». Modele fidele au parseur du jeu (GetDataPairs) :
// une ligne = des SEGMENTS separes par des virgules top-level, chaque segment
// est une paire « cle: valeur » (cle quelconque, espaces et vide tolerees) ;
// segments sans ':' legaux uniquement apres '{' (noms d'en-tete/parent) et au
// niveau 0 (bannieres ignorees par le jeu — vecu BlocksConfig 27486).
string? CheckEcf(string path)
{
    string[] lines;
    try { lines = File.ReadAllLines(path, Encoding.UTF8); }
    catch (Exception ex) { return $"ligne 0 : fichier illisible ({ex.Message})"; }

    int depth = 0;                    // profondeur d'accolades
    bool inLineHeader = false;        // juste apres '{' : noms d'en-tete sans ':'
    bool inBlockComment = false;      // entre / * et * /
    bool inCdata = false;             // entre <![CDATA[ et ]]>

    for (int i = 0; i < lines.Length; i++)
    {
        var masked = MaskLine(lines[i], ref inBlockComment, ref inCdata);
        int col = 0;
        bool lineHasPair = false;     // une paire vue sur la ligne : la suite
        while (col < masked.Length)   // peut etre des valeurs continues (vecu
        {                             // corpus) « ChildShapes: A, B »

            char c = masked[col];
            if (c == ' ' || c == '	') { col++; continue; }
            if (c == '}')
            {
                if (depth == 0)
                    return $"ligne {i + 1}, col {col + 1} : accolade fermante sans ouvrante";
                depth--; inLineHeader = false; col++;
                // vecu corpus vanille (EClassConfig 1195) : « }==== banner ==== »
                // — la fin de ligne apres une fermeture niveau 0 est toleree
                if (depth == 0) break;
                continue;
            }
            if (c == '{')
            {
                depth++; inLineHeader = true; col++;
                continue;
            }
            if (c == ',') { col++; continue; }
            // segment : jusqu'a la prochaine virgule/accolade top-level
            int segStart = col;
            while (col < masked.Length && masked[col] is not (',' or '{' or '}'))
                col++;
            var seg = masked[segStart..col].Trim();
            if (seg.Length == 0) continue;
            if (seg.Contains(':')) { inLineHeader = false; lineHasPair = true; }
            if (lineHasPair) continue;    // paire, ou valeur qui la prolonge
            if (inLineHeader) continue;   // nom d'en-tete ou de parent
            if (depth == 0) break;        // banniere niveau 0 : ignoree par le jeu
            return $"ligne {i + 1}, col {segStart + 1} : '{seg}' hors structure (propriete sans ':' ?)";
        }
    }
    // accolades non fermees en fin de fichier : TOLEREE par le jeu — vecu sur
    // deux scenarios officiels (Rise of the Dark Faction
    // AdditionalPoiSpawning.ecf, Stranded at Nemesis Containers.ecf) qui
    // chargent malgre une '{' jamais fermee. Un '}' en trop reste une erreur.
    return null;
}

// Neutralise chaines quotees (contenu -> espaces, portee LIGNE comme le
// parseur du jeu : une quote non fermee est toleree), commentaires '#' et
// « // » fin de ligne, commentaires / * * / multilignes et sections CDATA.
string MaskLine(string line, ref bool inBlockComment, ref bool inCdata)
{
    var sb = new StringBuilder(line.Length);
    bool inString = false;
    for (int j = 0; j < line.Length; j++)
    {
        char c = line[j];
        if (inBlockComment)
        {
            if (c == '*' && j + 1 < line.Length && line[j + 1] == '/') { inBlockComment = false; j++; sb.Append("  "); }
            else sb.Append(' ');
            continue;
        }
        if (inCdata)
        {
            if (c == ']' && j + 2 < line.Length && line[j + 1] == ']' && line[j + 2] == '>')
            { inCdata = false; j += 2; sb.Append("   "); }
            else sb.Append(' ');
            continue;
        }
        if (inString)
        {
            if (c == '"') inString = false;
            sb.Append(' ');
            continue;
        }
        if (c == '"') { inString = true; sb.Append('"'); continue; }
        if (c == '#') break;
        // commentaire « // » (vecu corpus vanille FactionWarfare 3335) :
        // uniquement en position de token, jamais au milieu d'un chemin « a/b »
        if (c == '/' && j + 1 < line.Length && line[j + 1] == '/'
            && (j == 0 || line[j - 1] is ' ' or '	' or ',' or '{' or '}'))
            break;
        if (c == '/' && j + 1 < line.Length && line[j + 1] == '*') { inBlockComment = true; j++; sb.Append("  "); continue; }
        if (c == '!' && j + 8 < line.Length && line[j..(j + 9)] == "<![CDATA[") { inCdata = true; j += 8; sb.Append("        "); continue; }
        sb.Append(c);
    }
    return sb.ToString();
}
