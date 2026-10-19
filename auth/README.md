# auth

Registro, login, sesiones y logout, con contraseñas hasheadas de verdad.
Produce el **mismo `user_id`** que ya esperan `credentials_vault`,
`agent_runtime`, `stats` y el resto — ningún otro paquete se tocó.

```python
from auth.store import AuthStore
from auth.service import AuthService

svc = AuthService(AuthStore("auth.db"))
user_id, token = svc.sign_up("ana@ejemplo.com", "una-contraseña-larga")
user_id, token = svc.log_in("ana@ejemplo.com", "una-contraseña-larga")
user_id = svc.verify_session(token)     # lo que correría en cada request real
svc.log_out(token)
```

## Verificado de verdad (40 tests, `python -m unittest auth.tests.test_auth`)

Sin mocks: scrypt corre de verdad. Lo que más importa:
- El archivo `.db` se lee **como bytes crudos** y no contiene ni la contraseña ni un token de sesión utilizable.
- Intentos de inyección SQL en el email terminan en un login fallido normal.
- Un usuario autenticado nunca ve las credenciales de otro en `credentials_vault` (integración real).

## Tres cosas que salieron de MEDIR, no de leer el código

1. **Canal lateral de tiempo.** Mi primera versión decía "no revela si el email existe" — y el *mensaje* de error era idéntico, pero un email inexistente respondía en **0.0 ms** y uno existente con mala contraseña en **126 ms**. Cronometrando se enumeraban cuentas. Ahora siempre se calcula un scrypt (contra un hash de relleno si el email no existe): **89.4 ms vs 88.1 ms**. Hay un test que habría fallado con la versión vieja.
2. **Sin bloqueo.** scrypt encarece cada intento pero no frena a un atacante paciente. Ahora: 5 intentos fallidos en 15 min bloquea el email (incluso con la contraseña correcta). Se cuenta por *string de email*, exista o no la cuenta, para que el bloqueo tampoco delate qué cuentas existen.
3. **Tokens de sesión en claro.** Se guardaban tal cual; con el `.db` filtrado se podían usar sesiones activas. Ahora se guarda el SHA-256 del token.

## Decisión que conviene que conozcas: scrypt, no bcrypt

El plan original era bcrypt. El entorno donde se construyó perdió la red y sus paquetes, y bcrypt no viene con Python; scrypt (`hashlib.scrypt`) sí. Es una alternativa técnicamente sólida (memory-hard, resiste GPU), no un parche. El hash guardado lleva el prefijo `scrypt$...`, así que pasar a bcrypt/argon2id es un cambio de **un archivo** (`passwords.py`) sin invalidar cuentas existentes.

## Lo que esto NO es (límites reales)

- **No hay API HTTP.** No existen los endpoints `/signup` `/login`; esto es la lógica que esos endpoints llamarían. El prototipo de React **no puede** conectarse a esto todavía: no hay servidor desplegado.
- **No hay límite por IP** (no hay IP en esta capa): vive en la capa HTTP.
- **El bloqueo por email es un arma de doble filo:** alguien puede bloquearle el login a una víctima fallando 5 veces a propósito (15 min). Mitigaciones para la capa HTTP: combinar con IP, CAPTCHA, avisar por mail.
- **Registrarse con un email usado sí revela que existe.** Cerrarlo del todo requiere verificación por email.
- **Faltan** verificación de email, recuperar contraseña y **2FA**. El 2FA importa antes de dinero real: tomar una cuenta = poder operar y modificar agentes (las API keys no retiran fondos, pero se puede operar mal con ellas).
- La clave maestra de la bóveda **no** deriva de la contraseña del usuario: quien tome la cuenta tiene acceso operativo a sus exchanges conectados.
- Cómo viaja el token (cookie `HttpOnly; Secure` o header) es decisión de la capa HTTP, aún no tomada.
