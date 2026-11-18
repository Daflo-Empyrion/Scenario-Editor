# Frontier-FR — rareté des ressources dans la galaxie

> Méthode : recensement des **gisements** (`RandomResources:`/`FixedResources:`
> des `playfield_static.yaml`) et des **roches collectibles** (décorations
> `RockResource*` des `*dynamic*.yaml`) sur les **204 playfields** du
> scénario. Une ressource est présente dans X % des playfields.
> Généré le 15/11/2026 — mesuré sur `C:\Dev\Frontier-FR`.

## Du plus rare au plus commun

| % galaxie | Ressource | Gisements | Roches collectibles |
|---:|---|---:|---:|
| **2.9 %** | Aluminium | 3 | 4 |
| **4.9 %** | Titan | 10 | — |
| **9.3 %** | Erestrum | 12 | 9 |
| **9.8 %** | Platine | 3 | 17 |
| **12.3 %** | Zascosium | 8 | 19 |
| **13.2 %** | Pentaxid | 27 | — |
| **14.2 %** | Sathium | 8 | 23 |
| **24.0 %** | Néodyme | 7 | 45 |
| **24.5 %** | Magnésium | 22 | 36 |
| **28.9 %** | Or | 19 | 50 |
| **32.4 %** | Carbone | 7 | 66 |
| **35.3 %** | Prométhium | 41 | 49 |
| **35.8 %** | Cobalt | 25 | 64 |
| **42.6 %** | Cuivre | 35 | 82 |
| **43.6 %** | Silicium | 37 | 88 |
| **46.1 %** | Fer | 42 | 88 |



## En orbite — champs d'astéroïdes miniers

> 92 secteurs d'orbite ont des champs d'astéroïdes ; % = part de ces
> secteurs qui contiennent le minerai. La **glace vient d'ici** (aucun
> gisement planétaire) ; **Carbone** est le minéral orbital le plus rare.

| % des orbites | Minerai | # secteurs |
|---:|---|---:|
| **14.1 %** | **Carbone** | 13 |
| **27.2 %** | **Platine** | 25 |
| **27.2 %** | **Aluminium** | 25 |
| **45.7 %** | **Néodyme** | 42 |
| **53.3 %** | **Zascosium** | 49 |
| **53.3 %** | **Erestrum** | 49 |
| **54.3 %** | **Magnésium** | 50 |
| **58.7 %** | **Fer** | 54 |
| **63.0 %** | **Sathium** | 58 |
| **64.1 %** | **Cobalt** | 59 |
| **64.1 %** | **Glace** | 59 |
| **65.2 %** | **Silicium** | 60 |
| **65.2 %** | **Cuivre** | 60 |
| **68.5 %** | **Titan** | 63 |
| **69.6 %** | **Or** | 64 |
| **82.6 %** | **Pentaxid** | 76 |
| **84.8 %** | **Prométhium** | 78 |

## Notes
- **Aluminium** est la ressource la plus rare de la galaxie (6 playfields,
  3 gisements seulement) — proche de **Titan** (10 playfields, uniquement
  en gisement, aucune roche collectible).
- **Pentaxid** : uniquement en gisement (27 playfields) — aucune roche
  collectible n'en contient.
- **Erestrum / Platine / Zascosium / Sathium** : le quatuor « endgame »,
  chacun dans ~10-25 % des playfields, en gisements ET roches.
- **La glace n'existe pas en gisement planétaire** (l'unique `IceResource`
  recensé est une décoration de `Scorched`) — elle vient des **champs
  d'astéroïdes en orbite** (64 % des secteurs miniers, voir section ci-dessus).
- Fer / Silicium / Cuivre : partout (~40-46 %) — base commune.


## Les coffres des donjons abandoned (pool planète)

> Recensement des **344 conteneurs** dans les 25 `.epb` du pool abandoned
> (groupes AbandonedPOI + 13 autres, cf. mapping `…rontierFR`).
> Moyenne : ~14 coffres par donjon.

| Type de coffre | Nb | % des coffres |
|---|---:|---:|
| AlienContainer (standard) | 20 | 5.8 % |
| **AlienContainerRare** | **19** | **5.5 %** |
| CargoPalette01/02/03/04 | 62 | 18.0 % |
| **AlienContainerVeryRare** | **16** | **4.7 %** |
| LockerWShelves | 15 | 4.4 % |
| ContainerMS01-05Large | 67 | 19.5 % |
| CargoContainerSmall/Medium | 29 | 8.4 % |
| ScifiContainer1/2/Energy/PowerLarge | 50 | 14.5 % |
| Props6BoxLarge/Medium | 24 | 7.0 % |
| ContainerAmmoLarge/Small | 7 | 2.0 % |
| ContainerController/Extension | 10 | 2.9 % |
| **AlienContainerUltraRare** | **10** | **2.9 %** |

### Les coffres rares — où placer le token
- **AlienContainerRare** : 19 (≈0,8 par donjon)
- **AlienContainerVeryRare** : 16 (≈0,6 par donjon)
- **AlienContainerUltraRare** : 10 (≈0,4 par donjon) — **le coffre du token**

Total rares = 45 coffres = **13,1 % des coffres des donjons**. À noter :
ces noms de devices sont aussi les **groupes de loot** — le token se
greffe sur `AlienContainerUltraRare`/`VeryRare` dans `LootGroups.ecf`.
