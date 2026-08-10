# Changelog

## 0.3.0

- Read-only registerscan via de officiële Home Assistant WebSocket API toegevoegd.
- Entities zonder apparaat, apparaten zonder entities en lege gebieden worden informatief gerapporteerd.
- Gebroken device-, area-, parent-device- en config-entryverwijzingen worden voor handmatige beoordeling gemarkeerd.
- Ingeschakelde entities zonder actuele state worden voor handmatige beoordeling gemarkeerd.
- Uitgeschakelde entities en `unavailable` states worden zonder cleanupadvies geïnventariseerd.
- Registerbevindingen toegevoegd aan JSON-, CSV- en Markdownrapporten en aan een eigen UI-tab.

## 0.2.1

- Ongeldige Python-basisimage vervangen door de officiële multi-architecture
  `ghcr.io/home-assistant/base-python:3.13-alpine3.24` image.

## 0.2.0

- Home Assistant-configuratiemount gewijzigd naar read-only.
- Audit-only status expliciet toegevoegd aan API en interface.
- Persistente JSON-, CSV- en Markdown-rapporten toegevoegd.
- Downloadacties voor rapporten toegevoegd.
- Offline auditcommando toegevoegd.
- Git-installatieklare app-repositorystructuur toegevoegd.

## 0.1.0

- Eerste lokale scanbackend en Ingress-interface.
- Veilige, review- en beschermde classificaties.
- Bewaarbeleid van 1 tot 10 dagen en back-updialoog voorbereid.
- Destructieve uitvoering hard uitgeschakeld.
