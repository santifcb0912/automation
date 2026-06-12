# Como compartir este proyecto

## Problema detectado

Google Chat elimina el archivo si el ZIP incluye credenciales, tokens, ejecutables,
caches o archivos generados. En este proyecto esos elementos son:

- `.env`
- `config/google_credentials.json`
- `config/google_oauth_client_secret.json`
- `config/google_oauth_token.json`
- `screenshots/`
- `__pycache__/` y `*.pyc`
- entornos virtuales como `venv/`, `env/` o `xlr8/`

## Forma recomendada para entregar a la empresa

1. Compartir el codigo sin secretos.
2. La empresa crea sus propias credenciales de Google.
3. Cada persona crea su propio entorno virtual:

   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```

4. Cada persona copia `.env.example` a `.env` y completa los valores.
5. Las credenciales se comparten por un canal seguro, separado del ZIP del codigo.

## Configuracion recomendada para empresa

Usar `GOOGLE_AUTH_MODE=service_account`.

Eso significa que el proyecto usara una cuenta tecnica de Google Cloud, propiedad
de la empresa, en lugar de depender de la cuenta personal de quien desarrollo el
proyecto.

El `.env` de cada persona debe quedar parecido a esto:

```env
INCONCERT_USER=usuario_asignado
INCONCERT_PASSWORD=password_asignado
GOOGLE_SHEET_ID=id_del_sheet_empresarial
GOOGLE_AUTH_MODE=service_account
GOOGLE_CREDENTIALS_PATH=./config/google_credentials.json
GOOGLE_DRIVE_FOLDER_NAME=Capturas UTEL
LEAD_TIMEOUT_SECONDS=120
LEAD_RETRY_INTERVAL_SECONDS=30
MAX_WORKERS=3
PORT=8000
```

## Pasos para crear la cuenta de servicio

Estos pasos los debe hacer alguien con acceso al Google Cloud de la empresa:

1. Crear o seleccionar un proyecto de Google Cloud de la empresa.
2. Habilitar las APIs:
   - Google Sheets API
   - Google Drive API
3. Crear una cuenta de servicio.
4. Crear una clave JSON para esa cuenta de servicio.
5. Guardar esa clave como:

   ```text
   config/google_credentials.json
   ```

6. Abrir el JSON y copiar el valor de `client_email`.
7. Compartir el Google Sheet con ese `client_email` como editor.
8. Compartir tambien la carpeta de Google Drive donde se subiran capturas, si el
   proyecto sube archivos a Drive.

El correo suele verse asi:

```text
nombre-servicio@proyecto-empresa.iam.gserviceaccount.com
```

## Como tu companero puede manipular el proyecto

Lo ideal es que el proyecto quede en un repositorio Git de la empresa, no solo en
un ZIP. Asi tu companero puede hacer cambios, revisar historial y mantenerlo
despues de tu salida.

Flujo recomendado:

1. Subir el codigo limpio a un repositorio de la empresa.
2. Agregar a tu companero como colaborador del repositorio.
3. No subir `.env` ni `config/google_credentials.json`.
4. El companero clona el repositorio:

   ```powershell
   git clone URL_DEL_REPOSITORIO
   cd utel-automation
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   copy .env.example .env
   ```

5. El companero recibe por canal seguro:
   - `.env` o los valores para llenarlo
   - `config/google_credentials.json`
6. Ejecuta:

   ```powershell
   python main.py
   ```

Si no usaran Git, entregar el ZIP limpio del codigo y enviar credenciales por
canal seguro separado.

## Credenciales necesarias

Para ejecutar el proyecto, el companero necesita:

- Usuario y password de InConcert para `INCONCERT_USER` e `INCONCERT_PASSWORD`.
- ID del Google Sheet para `GOOGLE_SHEET_ID`.
- Si se usa cuenta de servicio: `config/google_credentials.json`.
- Si se usa OAuth de usuario: `config/google_oauth_client_secret.json`.

No se recomienda compartir `config/google_oauth_token.json`: ese archivo representa
una sesion autorizada. Es mejor que cada usuario genere su propio token al iniciar
sesion desde su PC.

Para entrega empresarial con `service_account`, normalmente no se necesita
compartir `google_oauth_client_secret.json` ni `google_oauth_token.json`.

## Como pasar credenciales

Opciones recomendadas:

- Gestor de contrasenas empresarial o personal.
- Google Drive con acceso restringido solo al companero.
- ZIP cifrado con contrasena usando 7-Zip, enviando la contrasena por otro canal.
- Crear credenciales nuevas para el companero y revocar las antiguas si ya se
  compartieron por Chat.

No enviar `.env`, JSON de Google ni tokens directamente por Google Chat.
