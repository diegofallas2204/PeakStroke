# El piloto: PeakStroke en la red local

> 2026-11-17. Antes de pagar alojamiento, un equipo prueba la app de verdad
> (con login) servida desde esta computadora. Varias personas entran a la vez,
> cada una con su cuenta, para comprobar que lo que hace una le llega a las demás.

## Arrancar

En PowerShell, desde la carpeta `peakstroke`:

```powershell
.\piloto.ps1
```

Prepara todo la primera vez (un secreto propio, la base `backend\piloto.db` y la
build) y arranca. Escribe las direcciones de entrada:

```
esta computadora:  http://localhost:4173
                   http://127.0.0.1:4173
la wifi:           http://192.168.x.x:4173
```

**Ctrl+C** para parar. La base del piloto es aparte: no toca la de desarrollo.
Cierra antes el entorno de desarrollo (usa el puerto 8000).

## Las cuentas

Dos caminos:

- **Para probar ya**, el seed: 2 entrenadores, 5 atletas, un macrociclo en su
  semana 7 con tiempos, tests y sesiones. **Borra lo que hubiera en la base del
  piloto.** La contraseña de todas es `peakstroke`.

  ```powershell
  .\piloto.ps1 datos
  ```

  | Cuenta | Rol |
  |---|---|
  | `coach@peakstroke.dev` | entrenador, dueño del club |
  | `asistente@peakstroke.dev` | entrenador (no dueño) |
  | `sofia@peakstroke.dev`, `carlos@peakstroke.dev` | atletas con ficha y plan |
  | `sinplan@`, `sinficha@`, `debaja@`, `sinequipo@peakstroke.dev` | los casos raros |

- **Con el equipo real**: el club y su entrenador se crean aquí (la contraseña
  temporal se enseña una vez y obliga a cambiarla al entrar):

  ```powershell
  .\piloto.ps1 ops crear-equipo --nombre-equipo "Club" --correo entrenador@club.com --nombre "Nombre"
  ```

  Los atletas, mejor desde la app: el entrenador los invita por correo en
  **Atletas** (crea ficha, cuenta y código de una vez). Otros comandos (otro
  entrenador, restablecer contraseñas, revocar) en `backend/tools/README.md`.

## Varias cuentas a la vez

**Un navegador es una cuenta.** Entrar con otra en el mismo navegador cierra la
anterior en todas sus pestañas, a propósito: que nadie herede los datos de otro.
Para tener varias abiertas a la vez, cada una necesita su propio «origen»:

- **Otros dispositivos** de la misma wifi (teléfonos, otra computadora): la
  dirección `http://192.168.x.x:4173`. Es lo más parecido al uso real.
- **En esta misma computadora**, cada una de estas cuenta como un navegador
  distinto: `http://localhost:4173`, `http://127.0.0.1:4173`,
  `http://192.168.x.x:4173`, una ventana de incógnito y otro navegador.

Si un teléfono no conecta, lo normal es el firewall de Windows: al arrancar por
primera vez puede preguntar si `node` puede recibir conexiones; hay que
permitirlo en **redes privadas**.

## Cuándo le llega a uno lo que hace otro

No hay avisos en vivo (no hay websockets). Lo que apunta una persona le aparece a
otra cuando su pantalla vuelve a pedir los datos:

- **al volver a la ventana o a la app** (cambiar de pestaña, desbloquear el
  teléfono) o al recuperar la conexión;
- **al navegar** a una vista cuyos datos tengan más de 30 segundos;
- al recargar.

Hasta el 2026-11-17 esto era 5 minutos y sin pedir al volver a la ventana, así
que el entrenador no veía el tiempo de su atleta ni recargando. Si en el piloto
hace falta que algo se vea **sin tocar nada** (un tablero en la piscina, por
ejemplo), se puede refrescar esa vista cada pocos segundos: avisarlo.

## Qué probar

Cada escenario con dos cuentas abiertas a la vez:

| Hace | Lo ve |
|---|---|
| Atleta apunta una sesión en **Entrenamiento** | Entrenador: su lista de sesiones y su carga |
| Entrenador registra el tiempo real de una semana en **Plan semanal** | Atleta: su plan, su progresión y su **Inicio** |
| Entrenador crea un macrociclo y lo asigna a un atleta | Atleta: **Plan semanal** e **Inicio** |
| Entrenador registra un test (aeróbico o de lactato) | Atleta: **Base aeróbica** (solo los suyos) |
| Entrenador revoca el acceso de un atleta (**Perfil → miembros**) o le restablece la contraseña | Atleta: queda fuera en su siguiente petición (se cortan sus sesiones) |
| Entrenador da de baja la ficha de un atleta | Atleta: sigue entrando, pero sin plan ni datos de esa ficha |
| Dos entrenadores editan lo mismo a la vez | Gana el último; ver si alguno pierde algo |

Y las fronteras: un atleta no tiene que ver nada de un compañero, ni por la
interfaz ni cambiando números en la barra de direcciones.

## Qué tiene de distinto de producción

Es la app de verdad, con login, pero **por http** (es la red de casa o del club):
la cookie de sesión no lleva `Secure`, que un navegador no guardaría por http.
**No sirve para internet**: para eso, `docs/DESPLIEGUE.md` (https, entorno
`production`). Cada dispositivo cuenta con su propia IP para el freno de
intentos de login (la vista previa se la pasa al backend en `X-Forwarded-For`).

## Empezar de cero

Para vaciar el piloto: parar, y borrar `backend\piloto.db` (o `.\piloto.ps1
datos` para recargar el seed). `backend\.env.piloto` guarda el secreto: si se
borra, se genera otro y todas las sesiones abiertas se cierran.
