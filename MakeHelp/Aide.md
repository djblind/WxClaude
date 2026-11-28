# Aide de WxClaude

WxClaude est une interface de bureau pour la ligne de commande Claude Code, utilisée en mode non interactif (`claude -p`).
Elle est conçue pour un usage avec lecteur d'écran et au clavier seul.
Elle utilise les contrôles natifs de Windows.
Ce n'est pas un terminal.

## Installation et configuration

### Claude Code (claude -p)

WxClaude a besoin du programme Claude Code.
Installez-le en suivant la [documentation de Claude Code](https://code.claude.com/docs/en/overview).

Vérifiez l'installation dans un terminal avec `claude --version`.

Si vous avez l'application Claude pour Windows, vous n'avez rien à installer : elle contient sa propre copie de Claude Code, que WxClaude trouve tout seul quand `claude` n'est pas dans le PATH.
S'il en trouve plusieurs (par exemple une par compte, si vous ouvrez l'application avec deux comptes), il prend la plus récente : c'est le même programme.
Le compte Claude utilisé par WxClaude ne dépend pas de cette copie : c'est celui avec lequel vous vous êtes connecté dans WxClaude (menu Outils, Se connecter à Claude).

Pour utiliser Claude Code, il est obligatoire de s'authentifier :

- dans un terminal, lancez `claude auth login` et suivez les instructions ;
- vérifiez avec `claude auth status`.

### Claude dans WxClaude

Dans l'onglet "Claude" des préférences, il sera possible de définir l'utilisation du programme Claude Code.

Notamment, le type d'interface est la façon dont les questions de permission de Claude parviennent à WxClaude.
Il s'applique au message suivant et peut être changé à tout moment.

- **Protocole stdio** (par défaut) :
toutes les questions de permission, les questions structurées de Claude et l'approbation de ses plans.
- **Hook HTTP** :
les questions de permission sur les outils. WxClaude démarre pour cela un serveur HTTP local sur 127.0.0.1.

Avec le hook HTTP, une question sans réponse dans le délai d'attente est refusée par Claude Code. Réglez ce délai (1 à 10 minutes) sur la même page.

Dans le mode de permission *Ne pas demander*, rien n'est demandé, quel que soit le type : tout ce qui n'est pas autorisé à l'avance par une règle est refusé. Pour que Claude agisse sans vous demander, choisissez plutôt le mode *Automatique*, qui ne bloque que les actions dangereuses.

## Fonctionnement

### Espaces de travail

Un espace de travail est simplement le dossier où Claude va travailler.
Ainsi, il est important de lui fixer des limites dans cet espace.
Pour cela, les Paramètres de l'espace de travail permettent de définir des règles de permission et des variables d'environnement.
Tous ces paramètres sont nativement partagés avec l'application Claude Code.

Toutefois, ces paramètres pourraient être modifiés sans réel avertissement, par exemple à la suite d'une opération Git, d'un écrasement, etc.
C'est pourquoi ces fichiers de paramètres sont sous surveillance, pour pouvoir indiquer tous les changements extérieurs à WxClaude.
En cas de doute, l'application pourra fonctionner en mode restreint, c'est-à-dire que les agents seront limités dans leurs actions.
Pour retrouver un fonctionnement normal, il suffira d'approuver le dossier dans les paramètres de l'espace de travail.

- Fichier > Ouvrir depuis les projets Claude liste les dossiers déjà utilisés avec Claude Code.
- Au démarrage, le dernier espace de travail est rouvert. Vous pouvez le désactiver dans les Préférences, page Général.

### Conversations

Une conversation appartient toujours à un espace de travail. Ouvrir un espace de travail charge sa conversation mémorisée, sinon la plus récente. Une conversation n'est jamais créée automatiquement.

- Conversation > Reprendre une conversation liste celles de l'espace de travail, la plus récente d'abord.
- Conversation > Actualiser la conversation relit le fichier de session.
- Conversation > Nouvelle branche de conversation copie la conversation sous un autre nom. Le texte reste affiché. La copie est faite par Claude Code avec le premier message de la branche ; la conversation d'origine ne change pas.
- Conversation > Supprimer la conversation met à la Corbeille de Windows ce que Claude Code garde de la conversation, après confirmation. Vous pouvez la récupérer depuis la Corbeille.
- Conversation > Modifier l'agent change l'agent de la conversation courante.
Changer de modèle fait perdre le cache de l'invite de la conversation. Changer l'effort ou le mode de permission ne le fait pas.

#### Conversation longue

Claude relit toute la conversation à chaque message. Plus elle est longue, plus chaque message consomme votre quota, même une petite question. Un premier message relit déjà environ 50 000 tokens : les consignes et les outils de Claude Code.

WxClaude mesure la taille de la conversation après chaque réponse. La boîte Statistiques la donne. Quand elle dépasse un seuil, WxClaude agit selon le réglage Préférences > Espace de travail > Conversation longue :

- Ne rien faire.
- Me prévenir (par défaut) : WxClaude le dit une fois. Ouvrez alors une nouvelle conversation, ou tapez /compact pour remplacer la conversation par un résumé.
- La compacter automatiquement : WxClaude envoie /compact tout seul. Claude garde un résumé et peut perdre des détails.

Le seuil se règle en milliers de tokens, de 20 à 1000. Il vaut 100 par défaut.

#### Reprendre après une pause

Claude garde en mémoire ce qu'il a déjà lu pendant une heure au plus. Reprendre une longue conversation après une pause coûte donc cher : il doit tout relire.

Si vous envoyez un message dans une longue conversation laissée depuis plus d'une heure, WxClaude vous propose de continuer dans une nouvelle conversation. Répondez Oui (c'est le choix par défaut) : la nouvelle conversation, nommée « (suite) », reçoit les derniers échanges de l'ancienne, et Claude reprend le travail directement. Ce résumé est fait par WxClaude et ne coûte aucun token.

Préférences > Espace de travail > Conversation longue après une pause : proposer (par défaut), continuer sans demander (utile quand vous n'êtes pas devant l'ordinateur) ou garder la conversation.

#### Sous-agents moins chers

WxClaude donne à Claude deux aides moins chères : un lecteur sur Haiku, qui lit et cherche sans rien modifier, et un exécutant sur Sonnet, pour le travail répétitif. Claude décide lui-même quand s'en servir ; le travail le plus lourd coûte alors moins de quota. Vous pouvez les retirer dans Préférences > Espace de travail.

### Agents

Un agent est un ensemble de caractéristiques, propre à un fournisseur.
Pour WxClaude, il se limite à un modèle, un effort et un mode de permission.
- Chaque conversation a son propre agent principal.
Configurable, indépendamment des autres conversations, dans une boîte de dialogue dédiée.
- Chaque espace de travail a son propre agent alternatif.
Configurable dans les paramètres de l'espace de travail.
Utile pour, par exemple, envoyer rapidement des messages avec un niveau d'effort faible, sans avoir à modifier l'agent principal de la conversation.

Dans les préférences, on peut définir :
- l'agent principal, par défaut pour une nouvelle conversation.
- l'agent alternatif, par défaut pour un nouvel espace de travail.

### Permissions

Quand Claude veut utiliser un outil que le mode de permission n'autorise pas, une boîte de dialogue pose la question. La barre d'état l'annonce.

- *Autoriser* autorise l'outil cette fois.
- *Toujours autoriser* écrit une règle dans `.claude/settings.local.json`, comme le fait Claude Code. Ce bouton apparaît quand Claude Code propose une règle.
- *Refuser* refuse. Vous pouvez saisir une explication envoyée à Claude.

Fermer la boîte avec Échap est un refus. Le premier champ décrit la demande et reçoit le focus initial.

Les paramètres de l'espace de travail permettent de donner à chaque outil une règle d'autorisation, de demande ou de refus. Le refus l'emporte sur la demande, et la demande sur l'autorisation.

## Interface utilisateur

### Zone de conversation

La zone de conversation affiche l'échange en lecture seule.
Vos prompts (messages) sont sous un titre de niveau 1.
Les réponses de Claude sont sous un titre de niveau 2.
Les raccourcis clavier classiques de navigation web sont utilisables (titre, liste, tableau).
Des fenêtres d'affichage adaptées facilitent la lecture de certains éléments (voir le menu contextuel).

### Prompt

Le prompt est le champ où vous écrivez votre message à Claude.
Il peut contenir plusieurs lignes. Son menu contextuel est celui de Windows.
Il est grisé tant qu'il n'y a pas de conversation active.

Deux boutons envoient le message : l'un avec l'agent de la conversation, l'autre avec l'agent alternatif.
Pendant que Claude répond, l'envoi est grisé. Le champ reste utilisable pour de la saisie.

Le bouton *Interrompre Claude* arrête la réponse et les programmes lancés par Claude.
Il n'est actif que pendant une réponse.

### Activité

Le champ *Activité* (Alt+T) montre ce que fait Claude pendant qu'il répond, une ligne par action :
- l'outil utilisé, avec le fichier ou la commande (« Claude : Bash python -I verif.py ») ;
- ce que Claude écrit entre deux actions ;
- les sous-agents qu'il lance, puis ce qu'ils font (« Sous-agent traducteur : Write dial_zh_03.json »).

Il se trouve après les boutons d'envoi quand on appuie sur Tab. Il est en lecture seule : on le parcourt avec les flèches.
Une nouvelle ligne ne vous déplace jamais, et rien n'est annoncé : vous le lisez quand vous voulez.
Pendant que vous êtes dans ce champ, dans une fenêtre comme les Préférences ou dans un autre programme, « Claude réfléchit » et « Claude utilise l'outil… » ne sont pas dits, pour ne pas couper votre lecture. Dans la fenêtre principale, ils sont dits au plus une fois toutes les 5 secondes. Ils restent toujours dans la barre d'état.
Il est vidé à chaque message envoyé. Il ne coûte aucun token : WxClaude reçoit déjà tout cela.
Les réflexions de Claude n'y sont pas, car Claude Code n'en donne pas le texte.

#### Suivre un fichier

Un long travail qui tourne sans Claude (une compilation, un banc d'essai, une traduction lancée à part) écrit souvent ce qu'il fait dans un fichier journal.
Outils > Suivre un fichier… : choisissez ce fichier ; ses 5 dernières lignes, puis chaque nouvelle ligne, s'affichent dans le champ Activité, précédées du nom du fichier.
Vous pouvez suivre plusieurs fichiers. Outils > Arrêter le suivi des fichiers arrête tout. Cela ne coûte aucun token.

### Barre d'état

La barre d'état a trois zones. Elle ne prend pas le focus : utilisez la commande de votre lecteur d'écran pour la lire.

- La position : `Message 3 sur 8` indique le message où se trouve le curseur parmi les vôtres. Elle est vide s'il n'y en a pas.
- L'étape : `Étape 2 sur 5 : sujet` indique la tâche de la liste de Claude qu'il vient de commencer. Elle est vide s'il n'y en a pas et quand WxClaude attend votre message.
- Le message : la dernière annonce.
Quand WxClaude est prêt à recevoir des messages, il l'indique avec les jauges de votre abonnement et l'heure où la limite de 5 heures se réinitialise, par exemple `Prêt, jauge à 9 %, se réinitialise à 13:40`. Le détail de toutes les jauges est dans Outils > Jauge d'utilisation (Ctrl+Maj+U).

### Annonces

WxClaude dit ce qui se passe à votre lecteur d'écran. Les annonces sont regroupées en catégories.

Dans l'onglet "Annonces" des préférences, vous choisissez pour chaque catégorie ce qui est fait.
Selon la catégorie : rien, un message, la lecture de la ligne, une boîte de dialogue ou un son.
Le choix "Annonces" coupe ou rétablit l'envoi vers le lecteur d'écran.

Les erreurs de Claude ouvrent toujours une boîte de dialogue.
Quel que soit l'état de sortie des annonces, elles sont toutes mémorisées dans un historique, consultable depuis l'aide.

#### Alertes de jauge

L'abonnement de Claude Code a deux jauges : la fenêtre de 5 heures et la semaine.
Chaque alerte est dite la première fois que la jauge atteint ou dépasse son seuil.
Les seuils sont ceux de Claude Code : 90 % pour les 5 heures, 25, 50 et 75 % pour la semaine.

Avec d'autres fournisseurs, les jauges et alertes ne seront pas disponibles.
Seul le solde, ou crédit, pourra être consulté dans la boîte de dialogue de jauge, pour ceux qui le fournissent.

### Tâches, plans et utilisation

Trois fenêtres d'information s'ouvrent à la demande. Elles montrent ce que WxClaude sait au moment de l'ouverture.
- La liste de tâches donne les tâches que Claude s'est fixées pour la conversation : numéro, sujet et état (en attente, en cours, terminée). Une ligne dit aussi ce qui la bloque. Le détail de la tâche choisie est dessous.
- Les plans sont ceux que Claude a écrits dans le mode de permission *Planifier seulement*. Ils sont en lecture seule : il n'y a rien à approuver ici.
- L'utilisation montre les jauges de l'abonnement et leur remise à zéro. Elle donne aussi des informations sur les jetons utilisés.

## Autres fournisseurs d'IA

Un fournisseur est une source de modèles autre que votre abonnement Claude : un service distant (DeepSeek, GLM, OpenRouter) ou un serveur sur votre machine (Ollama, LM Studio).
Seuls les fournisseurs proposant la prise en charge d'Anthropic sont utilisables avec WxClaude. Il devrait être possible d'élargir la liste en utilisant un relais, tel que LiteLLM.

Claude est toujours présent, c'est le choix par défaut, et il ne peut ni se modifier ni se supprimer.
Les fournisseurs sont communs à toute l'application, pas propres à un espace de travail.
L'utilisation de WxClaude avec un fournisseur est possible sans être identifié avec un compte Claude Code.

Dans les préférences, le formulaire d'un fournisseur permet de définir :

- un nom et une adresse (URL) ;
- une clé API, ou « aucune » pour un serveur local ;
- la liste des modèles disponibles et des variables de configuration.
- le moteur : Claude Code, l'Agent SDK pour les crédits API de l'abonnement, ou un autre compte Claude (voir plus bas) ;
- le chargement des modèles, pour un serveur local LM Studio (voir plus bas).

### Plusieurs comptes Claude

Si vous avez plusieurs comptes Claude (par exemple un compte personnel et un compte d'équipe), WxClaude peut les utiliser tous, sans vous déconnecter : quand le quota d'un compte est atteint, vous continuez la même conversation avec un autre.

1. Dans les préférences, page Fournisseurs, ajoutez un fournisseur et choisissez le moteur « Compte Claude (un autre compte d'un abonnement) ». L'adresse et les modèles ne servent pas : ce sont ceux de Claude.
2. Activez le bouton « Se connecter au compte ». WxClaude ouvre la page de connexion de Claude dans votre navigateur.
3. Dans le navigateur, connectez-vous avec le compte à ajouter et autorisez-le. Si le navigateur est déjà connecté à un autre compte, changez de compte sur claude.ai ou copiez l'adresse dans une fenêtre de navigation privée.
4. La page affiche un code : copiez-le, collez-le dans le champ Code de WxClaude et envoyez-le.
5. Validez le formulaire avec OK.

Le compte apparaît alors dans la boîte de dialogue Agent (Ctrl+Maj+A), avec les modèles et les efforts de Claude.
Les conversations et l'historique restent les mêmes pour tous les comptes.

La connexion d'un compte dure un an ; ensuite, supprimez-la et reconnectez-vous avec le même bouton.
Elle est chiffrée avec votre compte Windows, comme les clés des autres fournisseurs. Elle n'est pas masquée aux commandes de Claude, pour que tous les modes de permission marchent, y compris Automatique.
Les jauges d'utilisation (Ctrl+Maj+U) restent celles du compte principal, celui de « Se connecter à Claude ».

### Utiliser les crédits API de l'abonnement

Les abonnements Max, Ultra et Team donnent chaque mois des crédits pour l'API Anthropic.
Ces crédits ne paient pas Claude Code, mais ils paient l'Agent SDK, sur lequel WxClaude peut s'appuyer.
Une fois votre quota d'abonnement atteint, vous pouvez ainsi continuer avec ces crédits.

1. Sur claude.ai, dans les paramètres de facturation de l'organisation, activez les « API credits » et liez une organisation de la console.
2. Sur platform.claude.com, créez une clé API.
3. Dans les préférences de WxClaude, ajoutez un fournisseur : adresse `https://api.anthropic.com`, moteur « Agent SDK (crédits API de l'abonnement) », clé enregistrée par WxClaude, et les noms complets des modèles (par exemple `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`).
4. Choisissez ce fournisseur dans un agent, par exemple l'agent alternatif (Maj+Entrée).

La conversation reste la même : Claude Code et l'Agent SDK partagent l'historique.
Sans carte bancaire enregistrée sur la console, rien n'est facturé : une fois les crédits du mois épuisés, la réponse dit que le solde est insuffisant.
La transmission « Relayée » ne s'applique pas à ce moteur : la clé est alors transmise de façon masquée.

Une clé API ne permet pas de demander le solde restant. WxClaude additionne donc lui-même le coût de chaque message envoyé par ce moteur, au prix catalogue.
La boîte de dialogue de jauge indique, pour chaque fournisseur Agent SDK, ce qu'il a dépensé ce mois-ci, par exemple « API : 3.42 dollars dépensés ce mois-ci sur les crédits API ».
Le solde lui-même se lit sur la console d'Anthropic : platform.claude.com, page Billing (facturation).

### Changer de modèle local sans relancer WxClaude

Un serveur local garde ses modèles dans la mémoire de l'ordinateur, qui a rarement la place pour deux gros modèles.
Avec LM Studio, WxClaude peut charger lui-même le modèle de chaque message : dans le formulaire du fournisseur, choisissez « LM Studio » dans la liste « Chargement des modèles ».

Avant chaque message, WxClaude vérifie alors que le modèle choisi est chargé.
S'il ne l'est pas, il regarde s'il reste assez de mémoire à côté des modèles déjà chargés ; sinon, il les décharge, puis il charge le bon modèle.
WxClaude l'annonce : « Pas assez de mémoire : déchargement de… », puis « Chargement du modèle…, patience ».
Le premier message après un changement de modèle attend donc le chargement, qui peut prendre quelques minutes pour un gros modèle.

- Les noms des modèles du fournisseur sont les noms de LM Studio, par exemple `qwen3.5-122b-a10b-claudecode`.
- La variable `CLAUDE_CODE_MAX_CONTEXT_TOKENS` du fournisseur donne la taille du contexte avec laquelle le modèle est chargé, par exemple 131072.
- Si le serveur de LM Studio ne répond pas, WxClaude le démarre.
- Quand vous fermez WxClaude, il décharge de LM Studio les modèles qu'il a utilisés, pour libérer la carte graphique. Un modèle que vous avez chargé vous-même et que WxClaude n'a pas utilisé reste chargé.

#### Un modèle servi par llama.cpp

Certains modèles ne s'ouvrent pas encore dans LM Studio et tournent avec le serveur de llama.cpp (`llama-server`).
WxClaude peut aussi le démarrer lui-même : dans le formulaire du fournisseur, choisissez « Serveur llama.cpp (commande) » dans la liste « Chargement des modèles », et collez dans le champ « Commande du serveur » la ligne de commande complète du serveur (avec `--port` et `--alias`).

- L'adresse du fournisseur est celle du serveur, par exemple `http://127.0.0.1:8080`, et le nom du modèle est celui donné par `--alias`.
- Avant un message, si le serveur ne répond pas, WxClaude décharge les modèles de LM Studio pour libérer la carte graphique, démarre le serveur et attend qu'il soit prêt.
- Avant de charger un modèle de LM Studio, WxClaude arrête le serveur qu'il a démarré. Il l'arrête aussi quand vous quittez WxClaude.
- WxClaude n'arrête jamais un serveur que vous avez démarré vous-même.

Il suffit alors d'ouvrir WxClaude normalement : dans la boîte de dialogue Agent (Ctrl+Maj+A), vous choisissez Claude sur votre abonnement, l'Agent SDK sur les crédits API, ou l'un de vos modèles locaux.

### Protection des clés API

Les clés d'autorisation des fournisseurs sont chiffrées avec votre compte Windows.
Plusieurs méthodes de transmission des clés à Claude Code sont possibles :

- Masquée (par défaut) : les commandes que Claude exécute ne voient pas la clé, mais la CLI impose alors le mode de permission manuel. Les modes Plan, Accepter les modifications, Auto et Ne pas demander ne s'appliquent pas. Cela ne concerne pas un compte Claude : sa connexion n'est jamais masquée, pour que tous les modes marchent (celle du compte principal est de toute façon dans un fichier que les commandes peuvent lire).
- Partagée : tous les modes marchent, mais les commandes de Claude peuvent lire la clé, et une consigne cachée dans un fichier ou une page web pourrait la leur faire révéler.
- Relayée : la clé reste seulement dans WxClaude, derrière un petit relais sur votre ordinateur (`127.0.0.1`). Tous les modes marchent, au prix d'un mécanisme de fonctionnement plus complexe.

### Confidentialité

- Pour un fournisseur autre que Claude, la télémétrie et les envois non essentiels vers Anthropic sont désactivés.
- Aussi, les prompts et les réponses ne transiteront pas par les serveurs d'Anthropic.

### Particularités

- Avec un fournisseur autre que celui d'Anthropic, l'agent répondra toujours au nom de Claude.

## Déléguer des tâches à une IA locale

Pour des raisons économiques ou de confidentialité, il est possible d'utiliser une IA locale avec Claude Code.
Claude reste votre interlocuteur, qui va pouvoir externaliser certaines tâches.
WxClaude ne propose pas de configuration pour ce mode d'utilisation, mais certaines annonces lui sont dédiées.

Procédure simplifiée de mise en œuvre :

- Installer et configurer une IA en local (LM Studio, Ollama, ...).
- Installer et configurer un serveur MCP (MCP in LM Studio, ollama-mcp, ...).
- Déclarer le serveur MCP à Claude Code,
soit avec Claude Code, dans son interface ou en ligne de commande,
soit directement avec les fichiers `.claude.json` ou `.mcp.json`.
- Dans WxClaude, demander à Claude d'utiliser l'IA locale pour certaines tâches.