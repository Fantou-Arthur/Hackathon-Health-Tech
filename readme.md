Documentation API : Plateforme de Solidarité Générationnelle

Cette documentation détaille les points de terminaison (endpoints) de l'application, conçus selon une approche API First. Le système supporte la négociation de contenu, permettant aux outils externes de consommer des données structurées tandis que les utilisateurs accèdent à l'interface visuelle.

🔐 Authentification

La plupart des routes nécessitent une session active (gérée par Flask-Login).

Mode : Session-based Cookie.

Header recommandé : X-Requested-With: XMLHttpRequest pour les appels AJAX.

👤 Profil Utilisateur

Consultation de Profil (Hybride)
Retourne soit une page HTML, soit un objet JSON selon les en-têtes de la requête.

URL : /profile/int:user_id

Méthode : GET

Authentification : Requise

Négociation de contenu :

Pour recevoir du JSON : Inclure le header Accept: application/json ou ajouter le paramètre ?format=json à l'URL.

Par défaut : Retourne le rendu HTML (text/html).

Exemple de réponse JSON :

{ "id": 123, "name": "Jean Dupont", "email": "jean.dupont@example.com", "role": "jeune", "bio": "Étudiant en informatique, disponible pour aider." }

Consultation de Profil (API Dédiée)
Endpoint strictement réservé aux échanges de données.

URL : /api/profile/int:user_id

Méthode : GET

Réponse : Toujours application/json.

📅 Disponibilités et Réservations

Lister les créneaux disponibles
Récupère tous les créneaux qui n'ont pas encore été réservés.

URL : /api/availabilities

Méthode : GET

Format de réponse :

[ { "id": 1, "youth": "Alice Martin", "start_time": "2024-06-15 14:30" } ]

Créer une réservation
Permet à un senior de réserver un créneau spécifique.

URL : /api/bookings

Méthode : POST

Corps de la requête (JSON ou Form) :

availability_id (int, requis) : ID du créneau.

description (string, optionnel) : Message d'accompagnement.

Réponse API (si Content-Type: application/json) :

{ "status": "success", "message": "Réservation confirmée" }

🛠️ Instructions pour les Développeurs Externes

Forcer le mode API

Pour garantir que le serveur ne retourne pas de HTML (même sur les routes hybrides), utilisez l'une des trois méthodes suivantes :

Header HTTP : Accept: application/json

Header HTTP : Content-Type: application/json

Paramètre URL : ?format=json

Codes d'erreur standards

401 Unauthorized : Session expirée ou utilisateur non connecté.

404 Not Found : Ressource inexistante.

400 Bad Request : Format de données invalide ou créneau déjà réservé.

Dernière mise à jour : Février 2024
