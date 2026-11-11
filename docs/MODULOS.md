# Trabajar y publicar por módulos

> Desde el 2026-11-10. Para repartir lo que falta por módulos, depurar uno sin
> el ruido de los demás y publicar cada uno como su propia versión.

## Qué es un módulo

Cada sección del menú, nombrada por su ruta:

| Módulo | Ruta | Sección |
|---|---|---|
| `inicio` | `/` | Inicio |
| `macrociclos` | `/macrociclos` | Macrociclos |
| `atletas` | `/atletas` (y `/atletas/:id`) | Atletas y la página de cada uno |
| `pruebas` | `/pruebas` | Base aeróbica |
| `entrenamiento` | `/entrenamiento` | Entrenamiento |
| `plan-semanal` | `/plan-semanal` | Plan semanal (Plan, Progresión, Zonas) |
| `equipo` | `/equipo` | Tabla del equipo |
| `simulador` | `/simulador` | Simulador |

**No son módulos**, y están en cualquier versión: Perfil, Ajustes, el login y el
cambio de contraseña. Tampoco el **backend**: es uno para todos y ya protege cada
ruta por rol. Un módulo apagado es un alcance de la interfaz, no una frontera de
seguridad.

## Qué pasa con un módulo apagado

- No sale en el menú, ni en el escritorio ni en el móvil.
- Su ruta redirige a la primera sección que sí está, aunque se teclee.
- Los enlaces que llevaban a él dejan de serlo. Por ejemplo, en `modulo/inicio`
  la tarjeta «Atletas en plan» sigue mostrando el número pero no lleva a la
  Tabla del equipo, y el botón «Tabla del equipo» desaparece.
- En **Ajustes** se lee qué módulos trae la versión que tienes delante.

## Cómo se elige

Al arrancar Vite (`npm run dev` o `npm run build`), en este orden:

1. **`VITE_MODULOS`**, si está puesta: `VITE_MODULOS=inicio,atletas npm run dev`.
   `todos` o vacía, todos.
2. **El nombre de la rama**: en `modulo/<nombre>` solo ese módulo. En GitHub
   Actions se lee de `GITHUB_HEAD_REF`/`GITHUB_REF_NAME`.
3. En cualquier otra rama (`Preliminar`, `main`), todos.

Se decide por la rama, y no por un archivo dentro de ella, para que fusionar el
trabajo de `modulo/inicio` de vuelta no traiga el interruptor: si la rama
llevara un `.env` propio, `Preliminar` acabaría con un solo módulo.

Código: `frontend/modulosDeRama.ts` (qué módulos trae la versión) y
`frontend/src/lib/modulos.ts` (qué hace la interfaz con ellos). Tests en
`modulosDeRama.test.ts` y `src/lib/modulos.test.ts` (`npm test`).

## El flujo

```
Preliminar ──┬──────────────●──────────────●─────▶   (todos los módulos)
             │              ▲ merge        ▲ merge
             └─ modulo/inicio ─●──●──●─────┘           (solo Inicio)
                                     │
                                     └─ tag inicio-v0.1.0
```

1. **Rama del módulo**, desde `Preliminar`: `git switch -c modulo/<nombre> Preliminar`.
2. **Se trabaja ahí** lo que falte de ese módulo. Cada tarea o issue va con la
   etiqueta del módulo (`modulo:inicio`) para repartirlas.
3. **Se depura** con `npm run dev` en esa rama: la app solo enseña ese módulo.
4. **Versión del módulo**: con la rama en verde, un tag `<módulo>-v<x.y.z>`
   (`inicio-v0.1.0`) y su build (`npm run build`), que trae solo ese módulo.
5. **De vuelta**: PR de `modulo/<nombre>` a `Preliminar`. Como lo único que la
   rama cambia es código del módulo, se fusiona sin conflictos con los demás.
6. Mantén la rama al día con `git merge Preliminar` (o `rebase`) mientras dure.

**Lo que hay que saber**

- **Un módulo no siempre se basta solo.** Inicio lee datos que se crean en
  Macrociclos y Atletas: en `modulo/inicio`, sin datos sembrados, sale vacío.
  Para depurarlo se usa la base de desarrollo (`seed.py`) o un backend con datos.
- **Un cambio compartido** (componentes de `components/`, `lib/`, el backend)
  hecho en la rama de un módulo afecta a todos al fusionarlo. Si es grande,
  mejor en `Preliminar` y que la rama lo traiga con un merge.
- **El backend no se recorta.** Una versión de Inicio sirve con el mismo backend
  que la versión completa.
