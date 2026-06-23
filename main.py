"""
LauraAI — Backend
Plataforma de preparación laboral con IA
Autor: Laureano
Fecha: Junio 2026
"""

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
from typing import List, Optional
import anthropic
import PyPDF2
import io
import os
import smtplib
import gspread
from google.oauth2.service_account import Credentials
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="LauraAI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
templates = Jinja2Templates(directory="templates")

# ─────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────

def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        import json
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    gc = gspread.authorize(creds)
    sheet = gc.open("LauraAI-registros").sheet1
    return sheet

def guardar_registro(nombre: str, email: str, situacion: str):
    try:
        sheet = get_sheet()
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        sheet.append_row([nombre, email, situacion, fecha])
        return True
    except Exception as e:
        print(f"Error guardando en Sheets: {e}")
        return False

# ─────────────────────────────────────────────
# EMAIL DE BIENVENIDA
# ─────────────────────────────────────────────

def enviar_bienvenida(nombre: str, email: str):
    try:
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_PASSWORD")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"¡Bienvenido/a a LauraAI, {nombre}! 🎯"
        msg["From"] = gmail_user
        msg["To"] = email

        html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; margin: 0; padding: 20px;">
  <div style="max-width: 560px; margin: 0 auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 2px 20px rgba(0,0,0,0.08);">
    
    <div style="background: linear-gradient(135deg, #4f46e5, #7c3aed); padding: 40px 32px; text-align: center;">
      <div style="font-size: 40px; margin-bottom: 12px;">🎯</div>
      <h1 style="color: #fff; font-size: 24px; font-weight: 700; margin: 0;">¡Bienvenido/a a LauraAI!</h1>
      <p style="color: #c4b5fd; font-size: 15px; margin: 8px 0 0;">Tu entrenador personal de entrevistas con IA</p>
    </div>

    <div style="padding: 32px;">
      <p style="font-size: 16px; color: #1a1a2e; margin: 0 0 16px;">Hola <strong>{nombre}</strong>,</p>
      
      <p style="font-size: 15px; color: #555; line-height: 1.7; margin: 0 0 24px;">
        Nos alegra que te hayas sumado. Laura, tu reclutadora con IA, está lista para ayudarte a conseguir tu próximo empleo.
      </p>

      <div style="background: #f8f7ff; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
        <p style="font-size: 14px; font-weight: 600; color: #4f46e5; margin: 0 0 12px;">¿Qué podés hacer con LauraAI?</p>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div style="font-size: 14px; color: #444;">✅ <strong>Practicá entrevistas reales</strong> — Laura te hace preguntas como un reclutador real</div>
          <div style="font-size: 14px; color: #444;">✅ <strong>Mejorá tu CV</strong> — análisis detallado con sugerencias concretas</div>
          <div style="font-size: 14px; color: #444;">✅ <strong>Optimizá tu LinkedIn</strong> — aparecé más en búsquedas de reclutadores</div>
          <div style="font-size: 14px; color: #444;">✅ <strong>Feedback personalizado</strong> — sabés exactamente qué mejorar</div>
        </div>
      </div>

      <p style="font-size: 14px; color: #888; line-height: 1.6; margin: 0 0 24px;">
        Si tenés alguna pregunta o sugerencia, respondé este email directamente. Leo todos los mensajes.
      </p>

      <p style="font-size: 15px; color: #1a1a2e; margin: 0;">
        ¡Mucho éxito en tu búsqueda!<br>
        <strong>El equipo de LauraAI</strong>
      </p>
    </div>

    <div style="background: #f8f7ff; padding: 20px 32px; text-align: center;">
      <p style="font-size: 12px; color: #aaa; margin: 0;">LauraAI · Tu entrenador de entrevistas con IA</p>
    </div>

  </div>
</body>
</html>
"""

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, email, msg.as_string())

        return True
    except Exception as e:
        print(f"Error enviando email: {e}")
        return False

# ─────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────

class Mensaje(BaseModel):
    role: str
    content: str

class SesionRequest(BaseModel):
    puesto: str
    nivel: str
    historial: List[Mensaje] = []
    respuesta_usuario: Optional[str] = None
    modo: str = "rapida"
    cv_analisis: Optional[str] = None
    empresa: Optional[str] = None

class FeedbackRequest(BaseModel):
    puesto: str
    historial: List[Mensaje]

class RegistroRequest(BaseModel):
    nombre: str
    email: str
    situacion: str

# ─────────────────────────────────────────────
# PROMPT DEL SISTEMA
# ─────────────────────────────────────────────

def get_system_prompt(puesto: str, nivel: str, modo: str = "rapida", empresa: Optional[str] = None) -> str:
    max_preguntas = 5 if modo == "rapida" else 8

    contexto_empresa = ""
    if empresa:
        contexto_empresa = f"""
CONTEXTO DE LA EMPRESA:
Estás reclutando para {empresa}. Actuá como reclutadora de esa empresa específica.
Adaptá las preguntas al tipo de empresa, industria y cultura que representás.
Si el candidato te pregunta sobre la empresa, respondé con información general coherente.
Cuando evalúes las respuestas del candidato, tené en cuenta el contexto de {empresa}."""

    return f"""Sos Laura, una reclutadora senior con 10 años de experiencia en empresas tecnológicas y de datos en Argentina. Sos profesional pero cercana, directa y empática.
{contexto_empresa}
Tu tarea es simular una entrevista laboral real para el puesto de {puesto} nivel {nivel}.

REGLA MÁS IMPORTANTE: Tenés exactamente {max_preguntas} preguntas para hacer en total. Ni una más. Cuando el candidato responda la pregunta número {max_preguntas}, cerrás la entrevista amablemente y escribís exactamente: ENTREVISTA_FINALIZADA

INSTRUCCIONES:
- Hacé UNA sola pregunta por vez. Nunca hagas varias preguntas juntas.
- No hagas preguntas de seguimiento — cada pregunta cuenta para el total.
- Llevá la cuenta interna de cuántas preguntas hiciste.
- Al llegar a {max_preguntas} preguntas respondidas, cerrá la entrevista inmediatamente.
- Hablás en español argentino, de manera natural y profesional.
- No revelés que sos una IA a menos que te lo pregunten directamente.

ESTRUCTURA DE {max_preguntas} PREGUNTAS:
1. Presentación ("Contame sobre vos")
2. Experiencia laboral más relevante
3. Pregunta técnica específica del puesto
4. Situación difícil que hayas manejado
5. Motivación y expectativas para {"esta empresa" if empresa else "este puesto"}{"" if max_preguntas == 5 else """
6. Trabajo en equipo o liderazgo
7. Pregunta técnica avanzada
8. Cierre (¿tenés preguntas para nosotros?)"""}

Empezá la entrevista de forma natural y amigable."""

# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {"mensaje": "LauraAI API funcionando", "version": "1.0.0"}

@app.get("/app")
async def frontend(request: Request):
    return templates.TemplateResponse(request, "index.html", {})

@app.post("/registro")
async def registrar_usuario(request: RegistroRequest):
    """Registra un nuevo usuario en Google Sheets y envía email de bienvenida"""
    try:
        if not request.nombre or not request.email:
            raise HTTPException(status_code=400, detail="Nombre y email son requeridos")

        sheets_ok = guardar_registro(request.nombre, request.email, request.situacion)
        email_ok = enviar_bienvenida(request.nombre, request.email)

        return {
            "ok": True,
            "sheets": sheets_ok,
            "email": email_ok,
            "mensaje": f"¡Bienvenido/a {request.nombre}! Revisá tu email."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/entrevista/iniciar")
async def iniciar_entrevista(request: SesionRequest):
    try:
        system_prompt = get_system_prompt(request.puesto, request.nivel, request.modo, request.empresa)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": "Iniciá la entrevista"}]
        )
        mensaje_ia = response.content[0].text
        return {
            "mensaje": mensaje_ia,
            "finalizada": False,
            "historial": [
                {"role": "user", "content": "Iniciá la entrevista"},
                {"role": "assistant", "content": mensaje_ia}
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/entrevista/responder")
async def responder_entrevista(request: SesionRequest):
    try:
        if not request.respuesta_usuario:
            raise HTTPException(status_code=400, detail="Falta la respuesta del usuario")
        system_prompt = get_system_prompt(request.puesto, request.nivel, request.modo, request.empresa)
        mensajes = [{"role": m.role, "content": m.content} for m in request.historial]
        mensajes.append({"role": "user", "content": request.respuesta_usuario})
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=system_prompt,
            messages=mensajes
        )
        mensaje_ia = response.content[0].text
        finalizada = "ENTREVISTA_FINALIZADA" in mensaje_ia
        mensaje_limpio = mensaje_ia.replace("ENTREVISTA_FINALIZADA", "").strip()
        mensajes.append({"role": "assistant", "content": mensaje_ia})
        return {
            "mensaje": mensaje_limpio,
            "finalizada": finalizada,
            "historial": mensajes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/entrevista/feedback")
async def generar_feedback(request: FeedbackRequest):
    try:
        historial_texto = ""
        for m in request.historial:
            rol = "Reclutadora" if m.role == "assistant" else "Candidato"
            historial_texto += f"{rol}: {m.content}\n\n"

        prompt = f"""Analizá esta entrevista para el puesto de {request.puesto} y generá feedback detallado y constructivo.

TRANSCRIPCION:
{historial_texto}

## Evaluacion general
[Puntaje del 1 al 10 con justificación]

## Puntos fuertes
[3 puntos concretos con ejemplos]

## Areas de mejora
[3 puntos concretos con ejemplos y cómo reformularlos]

## Respuestas destacadas
[La mejor respuesta y por qué fue efectiva]

## Consejos para proximas entrevistas
[3 consejos prácticos para el mercado argentino]

## Proximos pasos recomendados
[Qué debería hacer esta semana]

Importante: no penalices respuestas genéricas por falta de contexto sobre la empresa. Sé honesto, constructivo y específico."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        return {"feedback": response.content[0].text, "puesto": request.puesto}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cv/analizar")
async def analizar_cv(file: UploadFile = File(...), puesto: str = "Analista de Datos"):
    try:
        contenido = await file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contenido))
        texto_cv = ""
        for pagina in pdf_reader.pages:
            texto_cv += pagina.extract_text()
        if not texto_cv.strip():
            raise HTTPException(status_code=400, detail="No se pudo extraer texto del PDF")

        prompt = f"""Analizá este CV para el puesto de {puesto} en el mercado argentino.

CV:
{texto_cv}

## Puntaje general
[Del 1 al 10 con justificación]

## Fortalezas del CV
[3 puntos concretos]

## Mejoras urgentes
[3 cambios concretos a hacer YA]

## Palabras clave faltantes
[Keywords importantes que no aparecen]

## Sección más débil
[Cuál es y cómo mejorarla]

## Recomendación final
[El consejo más importante]

S� específico y orientado al mercado de datos en Argentina."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        return {"analisis": response.content[0].text, "puesto": puesto, "paginas": len(pdf_reader.pages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/linkedin/analizar")
async def analizar_linkedin(request: dict):
    try:
        perfil_texto = request.get("perfil", "")
        puesto_objetivo = request.get("puesto_objetivo", "Analista de Datos")
        if not perfil_texto.strip():
            raise HTTPException(status_code=400, detail="El perfil no puede estar vacío")

        prompt = f"""Analizá este perfil de LinkedIn para alguien que busca trabajo como {puesto_objetivo} en el mercado argentino.

PERFIL:
{perfil_texto}

## Puntaje general
[Del 1 al 10 con justificación]

## Título profesional
[Evaluá el actual y sugerí uno mejor optimizado para búsquedas]

## Resumen (About)
[Evaluá el actual y escribí uno mejorado listo para copiar y pegar]

## Experiencia laboral
[3 sugerencias concretas para mejorar cómo está presentada]

## Palabras clave faltantes
[Keywords que los reclutadores buscan y no aparecen]

## Visibilidad en búsquedas
[Consejos específicos para aparecer más en búsquedas]

## Recomendación principal
[El cambio más importante a hacer hoy]

S� específico y orientado al mercado argentino de datos y tecnología."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        return {"analisis": response.content[0].text, "puesto_objetivo": puesto_objetivo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/linkedin/analizar-pdf")
async def analizar_linkedin_pdf(file: UploadFile = File(...), puesto_objetivo: str = "Analista de Datos"):
    try:
        contenido = await file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contenido))
        texto = ""
        for pagina in pdf_reader.pages:
            texto += pagina.extract_text()
        if not texto.strip():
            raise HTTPException(status_code=400, detail="No se pudo extraer texto del PDF")

        prompt = f"""Analizá este perfil de LinkedIn exportado como PDF para alguien que busca trabajo como {puesto_objetivo} en el mercado argentino.

PERFIL:
{texto}

## Puntaje general
[Del 1 al 10 con justificación]

## Título profesional
[Evaluá el actual y sugerí uno mejor]

## Resumen (About)
[Evaluá el actual y escribí uno mejorado listo para copiar]

## Experiencia laboral
[3 sugerencias concretas]

## Palabras clave faltantes
[Keywords importantes que no aparecen]

## Visibilidad en búsquedas
[Consejos para aparecer más en búsquedas]

## Recomendación principal
[El cambio más importante hoy]

S� específico y orientado al mercado argentino."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        return {"analisis": response.content[0].text, "puesto_objetivo": puesto_objetivo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
