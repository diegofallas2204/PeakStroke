# Cheat-sheet de skills de Claude Code

Todos los skills disponibles en esta máquina, una oración por skill.
Orden: **gstack primero**, luego el resto por grupo.

- Skills globales en disco: `~/.claude/skills/<nombre>/SKILL.md`
- Se invocan escribiendo `/<nombre>`
- Última revisión: 2026-08-06

---

## 1. gstack — ciclo de desarrollo

### 1.1 Planificación y definición del trabajo

| Skill | Qué hace |
|---|---|
| `/gstack` | Router: manda tu petición al skill de gstack correcto cuando no sabes cuál usar. |
| `/office-hours` | Sesión estilo YC Office Hours para decidir si una idea vale la pena antes de construirla. |
| `/spec` | Convierte una intención vaga en un spec ejecutable en cinco fases y lo publica como issue. |
| `/autoplan` | Corre las cuatro revisiones de plan (CEO, diseño, ingeniería, DX) de una pasada y solo te frena en las decisiones de gusto. |
| `/plan-ceo-review` | Revisa el plan en modo fundador: ambición, alcance y si estás construyendo lo correcto. |
| `/plan-eng-review` | Revisa el plan en modo jefe de ingeniería: arquitectura, riesgos técnicos y viabilidad. |
| `/plan-design-review` | Revisa el plan con ojo de diseñador antes de que exista una sola línea de UI. |
| `/plan-devex-review` | Revisa el plan desde la experiencia de quien va a usar tu API, CLI o SDK. |
| `/plan-tune` | Ajusta cuántas preguntas te hacen los skills de plan según tu perfil de desarrollador. |

### 1.2 Implementación y debugging

| Skill | Qué hace |
|---|---|
| `/investigate` | Debugging sistemático en cuatro fases con ley de hierro: sin causa raíz no hay arreglo. |
| `/codex` | Pide una segunda opinión a Codex CLI de OpenAI sobre tu código o tu plan. |
| `/careful` | Activa avisos antes de ejecutar comandos destructivos. |
| `/guard` | Modo seguridad completo: avisos de comandos destructivos + edición limitada a un directorio. |
| `/freeze` | Restringe las ediciones de la sesión a un directorio concreto. |
| `/unfreeze` | Quita el límite de directorio puesto por `/freeze`. |

### 1.3 Calidad, QA y salud del código

| Skill | Qué hace |
|---|---|
| `/health` | Dashboard de calidad: corre type checker, linter, tests y detector de código muerto, y te da una nota de 0 a 10. |
| `/qa` | Prueba la app web de forma sistemática y arregla los bugs que encuentra, commit por commit. |
| `/qa-only` | Igual que `/qa` pero solo reporta: no toca tu código. |
| `/review` | Revisión previa al merge del diff contra la rama base (SQL, límites de confianza, efectos condicionales). |
| `/benchmark` | Detecta regresiones de rendimiento usando el navegador headless. |
| `/benchmark-models` | Compara cómo rinden los skills de gstack con distintos modelos. |
| `/retro` | Retrospectiva semanal de ingeniería: qué se envió y cómo fue. |
| `/learn` | Revisa, busca y limpia lo que gstack ha aprendido de tu proyecto entre sesiones. |

### 1.4 Seguridad

| Skill | Qué hace |
|---|---|
| `/cso` | Auditoría de seguridad completa: secretos, cadena de suministro, CI/CD, OWASP Top 10 y modelado STRIDE, en modo diario o mensual profundo. |

### 1.5 Diseño

| Skill | Qué hace |
|---|---|
| `/design-consultation` | Propone un sistema de diseño completo (estética, tipografía, color, layout, motion) tras investigar tu producto y el mercado. |
| `/design-shotgun` | Genera varias variantes de diseño, las abre en un tablero comparativo y recoge tu feedback. |
| `/design-html` | Genera el HTML/CSS final de calidad producción a partir del diseño elegido. |
| `/design-review` | QA visual: encuentra inconsistencias de espaciado, jerarquía rota y patrones de slop, y los arregla. |
| `/devex-review` | Audita la experiencia real de un desarrollador con tu producto, incluido el tiempo hasta el primer "hola mundo". |

### 1.6 Envío y despliegue

| Skill | Qué hace |
|---|---|
| `/ship` | Flujo completo de envío: merge de base, tests, review del diff, bump de versión, CHANGELOG, commit, push y PR. |
| `/land-and-deploy` | Mergea, despliega y verifica en un solo flujo. |
| `/landing-report` | Panel de solo lectura con el estado de la cola de envíos. |
| `/canary` | Monitorea producción justo después de un deploy para cazar regresiones temprano. |
| `/setup-deploy` | Configura los ajustes de despliegue que usa `/land-and-deploy`. |

### 1.7 Documentación y artefactos

| Skill | Qué hace |
|---|---|
| `/document-generate` | Escribe desde cero la documentación que falta de una feature, un módulo o el proyecto entero. |
| `/document-release` | Actualiza la documentación después de enviar algo. |
| `/make-pdf` | Convierte cualquier markdown en un PDF de calidad publicable. |
| `/diagram` | Convierte una descripción en español (o mermaid) en un diagrama editable `.excalidraw`. |

### 1.8 Navegador y datos web

| Skill | Qué hace |
|---|---|
| `/browse` | Navegador headless rápido para probar tu sitio y hacer QA. |
| `/open-gstack-browser` | Abre GStack Browser, un Chromium controlado por IA con la extensión de barra lateral. |
| `/setup-browser-cookies` | Importa las cookies de tu Chromium real para poder probar zonas autenticadas. |
| `/scrape` | Extrae datos de una página web. |
| `/skillify` | Convierte el último `/scrape` que funcionó en un skill de navegador permanente. |
| `/pair-agent` | Empareja un agente de IA remoto con tu navegador. |

### 1.9 Contexto y memoria

| Skill | Qué hace |
|---|---|
| `/context-save` | Guarda el estado de git, las decisiones tomadas y lo que queda pendiente. |
| `/context-restore` | Recupera el contexto guardado para continuar donde lo dejaste. |
| `/setup-gbrain` | Instala y configura gbrain, el índice semántico del código, para este agente. |
| `/sync-gbrain` | Mantiene gbrain al día con el código del repo y refresca la guía de búsqueda en CLAUDE.md. |

### 1.10 iOS (no aplica a PeakStroke)

| Skill | Qué hace |
|---|---|
| `/ios-qa` | QA en dispositivo real para apps SwiftUI. |
| `/ios-fix` | Arregla bugs de iOS de forma autónoma. |
| `/ios-design-review` | Auditoría visual de una app iOS en hardware real. |
| `/ios-sync` | Regenera el puente de depuración iOS contra las plantillas más recientes de gstack. |
| `/ios-clean` | Elimina el paquete DebugBridge y todo su cableado `#if DEBUG` de la app. |

### 1.11 Mantenimiento de gstack

| Skill | Qué hace |
|---|---|
| `/gstack-upgrade` | Actualiza gstack a la última versión. |

---

## 2. Orquestación propia

| Skill | Qué hace |
|---|---|
| `/run-gstack` | Corre la sesión de desarrollo de PeakStroke de principio a fin encadenando los skills de gstack en orden, con puertas de seguridad y QA que no se pueden saltar. |
| `/peakstroke` | Carga el contexto del proyecto PeakStroke desde el vault de Obsidian. |
| `/ro` | Lee el vault de Obsidian (`E:\Obsidian`) y construye el entendimiento del proyecto antes de trabajar. |
| `/wo` | Escribe al vault de Obsidian lo importante de la sesión como notas y nodos de conocimiento, y actualiza la memoria. |

---

## 3. Ingeniería (skills de Matt Pocock)

| Skill | Qué hace |
|---|---|
| `/grill-me` | Te interroga sin piedad sobre tu plan o diseño hasta que quede afilado. |
| `/tdd` | Desarrollo guiado por tests: rojo, verde, refactor, con tests de integración. |
| `/to-prd` | Convierte la conversación actual en un PRD y lo publica en el issue tracker, sin entrevista. |
| `/improve-codebase-architecture` | Escanea el código buscando oportunidades de profundizar, las presenta en un informe HTML y te interroga sobre la que elijas. |
| `/setup-matt-pocock-skills` | Configura el repo (issue tracker, etiquetas de triage, docs de dominio) antes de usar los skills anteriores. Se corre una sola vez. |

---

## 4. Obsidian y contenido web

| Skill | Qué hace |
|---|---|
| `/obsidian-cli` | Lee, crea, busca y gestiona notas del vault desde la línea de comandos, y depura plugins y temas. |
| `/obsidian-markdown` | Escribe markdown con sintaxis de Obsidian: wikilinks, embeds, callouts, propiedades y tags. |
| `/obsidian-bases` | Crea y edita ficheros `.base` con vistas, filtros, fórmulas y resúmenes tipo base de datos. |
| `/json-canvas` | Crea y edita canvas `.canvas` con nodos, aristas, grupos y conexiones para mapas mentales y diagramas. |
| `/defuddle` | Extrae markdown limpio de una página web quitando navegación y ruido, más barato que WebFetch. |

---

## 5. Frontend y diseño (plugins)

| Skill | Qué hace |
|---|---|
| `/impeccable` | Mejora cualquier interfaz: UX, jerarquía, accesibilidad, rendimiento, tipografía, motion y estados vacíos. |
| `/frontend-design` | Guía de dirección visual para que una UI nueva no se lea como una plantilla genérica. |
| `/taste-skill` | Skill anti-slop para landings y portafolios, con tres diales de variación, motion y densidad y ~80 chequeos previos. |
| `/emil-design-eng` | Aplica la filosofía de ingeniería de diseño de Emil Kowalski a animaciones y componentes interactivos. |
| `/review-animations` | Revisión agresiva de código de animación y motion; solo motion, nada más. |
| `/dataviz` | Reglas para que cualquier gráfico, dashboard o visualización se lea como un sistema coherente en claro y oscuro. |
| `design:design-critique` | Feedback estructurado de diseño sobre usabilidad, jerarquía y consistencia. |
| `design:accessibility-review` | Auditoría WCAG 2.1 AA: contraste, navegación por teclado, tamaño de objetivos táctiles y lectores de pantalla. |
| `design:design-system` | Audita, documenta o extiende tu sistema de diseño y caza valores hardcodeados. |
| `design:design-handoff` | Genera la especificación de entrega a desarrollo: tokens, props, estados, breakpoints y animaciones. |
| `design:ux-copy` | Escribe o revisa microcopy: mensajes de error, estados vacíos, CTAs y confirmaciones. |
| `design:user-research` | Planifica, conduce y sintetiza investigación de usuarios. |
| `design:research-synthesis` | Destila entrevistas, encuestas y tickets en temas, segmentos y recomendaciones priorizadas. |

---

## 6. Ingeniería (plugin `engineering`)

| Skill | Qué hace |
|---|---|
| `engineering:architecture` | Crea o evalúa un ADR cuando hay que elegir entre tecnologías y documentar las consecuencias. |
| `engineering:system-design` | Diseña sistemas, servicios, APIs y modelos de datos desde requisitos. |
| `engineering:code-review` | Revisa cambios buscando seguridad, rendimiento y corrección (N+1, inyección, casos borde). |
| `engineering:debug` | Sesión de debugging estructurada: reproducir, aislar, diagnosticar y arreglar. |
| `engineering:testing-strategy` | Diseña la estrategia y el plan de pruebas: qué probar, con qué cobertura y con qué arquitectura de tests. |
| `engineering:tech-debt` | Identifica, clasifica y prioriza la deuda técnica. |
| `engineering:deploy-checklist` | Checklist previo al despliegue: CI, aprobaciones, migraciones, feature flags y disparadores de rollback. |
| `engineering:incident-response` | Flujo de incidente: triaje, comunicación y postmortem sin culpables. |
| `engineering:documentation` | Escribe y mantiene documentación técnica: READMEs, runbooks, docs de API y guías de onboarding. |
| `engineering:standup` | Genera el parte diario a partir de commits, PRs y tickets recientes. |

---

## 7. Claude Code — configuración y utilidades

| Skill | Qué hace |
|---|---|
| `/init` | Crea el `CLAUDE.md` inicial documentando el codebase. |
| `/run` | Arranca la app del proyecto para ver un cambio funcionando de verdad, no solo en tests. |
| `/simplify` | Repasa el código cambiado buscando reuso, simplificación y eficiencia, y aplica los arreglos. |
| `/security-review` | Revisión de seguridad de los cambios pendientes en la rama actual. |
| `/update-config` | Configura `settings.json`: permisos, variables de entorno y hooks automáticos. |
| `/keybindings-help` | Personaliza los atajos de teclado en `~/.claude/keybindings.json`. |
| `/fewer-permission-prompts` | Analiza tus transcripciones y genera una allowlist para dejar de pedirte permiso por comandos de solo lectura. |
| `/loop` | Ejecuta un prompt o slash command en intervalos repetidos. |
| `/schedule` | Crea y gestiona agentes en la nube que corren con horario cron. |
| `/claude-api` | Referencia de la API de Claude: IDs de modelo, precios, streaming, tool use, MCP y caching. |
| `/artifact-design` | Fundamentos de diseño para páginas Artifact publicadas. |
| `/artifact-capabilities` | Capacidades de runtime que puede tener un Artifact (datos en vivo, estado compartido, auto-actualización). |

---

## 8. Plugin `anthropic-skills` y ofimática

| Skill | Qué hace |
|---|---|
| `anthropic-skills:xlsx` | Crea, lee y arregla hojas de cálculo `.xlsx`, `.csv` y `.tsv`. |
| `anthropic-skills:docx` | Crea, lee y edita documentos de Word `.docx` y plantillas `.dotx`. |
| `anthropic-skills:pptx` | Crea, lee y edita presentaciones `.pptx` y plantillas `.potx`. |
| `anthropic-skills:pdf` | Lee, combina, divide, rellena, cifra y hace OCR sobre PDFs. |
| `anthropic-skills:skill-creator` | Crea, mejora y mide el rendimiento de skills nuevos. |
| `anthropic-skills:consolidate-memory` | Repasa los ficheros de memoria: fusiona duplicados, corrige datos viejos y poda el índice. |
| `anthropic-skills:web-artifacts-builder` | Construye artifacts HTML complejos con React, Tailwind y shadcn/ui. |
| `anthropic-skills:schedule` | Crea o actualiza una tarea programada que corre sola. |
| `anthropic-skills:morning` | Renderiza tu resumen matutino como artifact HTML o lo programa a diario. |
| `anthropic-skills:setup-cowork` | Configura Cowork: instala plugins según tu rol y conecta tus herramientas. |
| `cowork-plugin-management:create-cowork-plugin` | Te guía para crear un plugin nuevo desde cero. |
| `cowork-plugin-management:cowork-plugin-customizer` | Adapta un plugin existente a las herramientas y flujos de tu organización. |
