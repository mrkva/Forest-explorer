# Habitat Explorer SK

Interactive map of Slovak forests and geology. Tap anywhere to identify habitat types, forest classification, and geological formations.

**Live:** [mrkva.github.io/slovak-habitat-explorer](https://mrkva.github.io/slovak-habitat-explorer/)

## Features

- **Forest data** — habitat type names, HSLT classification, commercial/protective status, stand area
- **Geological data** — lithological descriptions, geological era, formations
- **Layer control** — toggle Forest stands, Tree species, Forest types, and Geological map overlays
- **Per-layer opacity** — adjust transparency of each active overlay
- **Offline support** — save the current map area for offline use (PWA with service worker caching)
- **Mobile-friendly** — works as an installable app on iOS and Android

## Data sources

| Layer | Provider | Service |
|-------|----------|---------|
| Forest stands (JPRL) | [Národné lesnícke centrum](https://web.nlcsk.org) | WMS + ArcGIS REST |
| Forest types | [NLC](https://web.nlcsk.org) | WMS + ArcGIS REST |
| Tree species | [NLC](https://web.nlcsk.org) | WMS |
| Geological map 1:50k | [SGÚDŠ](https://www.geology.sk) | WMS + ArcGIS REST |

## Tech

Single-page app built with [Leaflet.js](https://leafletjs.com). No build step — just static HTML, JS, and a service worker.
