# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Module admin serveur (EWA) -- l'editeur est CLIENT de l'API REST du mod
EmpyrionWebAccess (GitHub-TC, GPL-3.0) installe sur le serveur dedie : aucun
code C# embarque, aucune derive de licence (client HTTP d'une API tierce).

Socle :
- config.py      : configuration persistee dans settings.json (cle "ewa")
- client.py      : client REST + JWT (requests), 1er login = compte admin
- telnet.py      : console telnet dediee (secours + envoi chat SAY)
- sftp_deploy.py : synchronisation MIROIR du scenario via SFTP (paramiko)
"""
