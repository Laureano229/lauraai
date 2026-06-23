"""
LauraAI — Backend
Plataforma de preparacion laboral con IA
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
import json
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

FECHA_ACTUAL = datetime.now().strftime("%B %Y")

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
        msg["Subject"] = f"Bienvenido/a a LauraAI, {nombre}!"
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
      <h1 style="color: #fff; font-size: 24px; font-weight: 700; margin: 0;">Bienvenido/a a LauraAI!</h1>
      <p style="color: #c4b5fd; font-size: 15px; margin: 8px 0 0;">Tu entrenador personal de entrevistas con IA</p>
    </div>

    <div style="padding: 32px;">
      <p style="font-size: 16px; color: #1a1a2e; margin: 0 0 16px;">Hola <strong>{nombre}</strong>,</p>

      <p style="font-size: 15px; color: #555; line-height: 1.7; margin: 0 0 24px;">
        Nos alegra que te hayas sumado. Laura, tu reclutadora con IA, esta lista para ayudarte a conseguir tu proximo empleo.
      </p>

      <div style="background: #f8f7ff; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
        <p style="font-size: 14px; font-weight: 600; color: #4f46e5; margin: 0 0 12px;">Que podes hacer con LauraAI?</p>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div style="font-size: 14px; color: #444;">Practica entrevistas reales — Laura te hace preguntas como un reclutador real</div>
          <div style="font-size: 14px; color: #444;">Mejora tu CV — analisis detallado con sugerencias concretas</div>
          <div style="font-size: 14px; color: #444;">Optimiza tu LinkedIn — aparece mas en busquedas de reclutadores</div>
          <div style="font-size: 14px; color: #444;">Feedback personalizado — sabes exactamente que mejorar</div>
        </div>
      </div>

      <p style="font-size: 14px; color: #888; line-height: 1.6; margin: 0 0 24px;">
        Si tenes alguna pregunta o sugerencia, respondé este email directamente. Leo todos los mensajes.
      </p>

      <p style="font-size: 15px; color: #1a1a2e; margin: 0;">
        Mucho exito en tu busqueda!<br>
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

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
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
# PROMPT DEL SISTEMA - ENTREVISTA
# ─────────────────────────────────────────────

def get_system_prompt(puesto: str, nivel: str, modo: str = "rapida", empresa: Optional[str] = None) -> str:
    max_preguntas = 5 if modo == "rapida" else 8

    contexto_empresa = ""
    if empresa:
        contexto_empresa = f"""
CONTEXTO DE LA EMPRESA:
Estas reclutando para {empresa}. Actua como reclutadora de esa empresa especifica.
Adapta las preguntas al tipo de empresa, industria y cultura que representas.
Si el candidato te pregunta sobre la empresa, responde con informacion general coherente.
Cuando evalues las respuestas del candidato, ten en cuenta el contexto de {empresa}."""

    return f"""Sos Laura, una reclutadora senior con 10 anos de experiencia en empresas tecnologicas y de datos en Argentina. Sos profesional pero cercana, directa y empatica.

La fecha actual es {FECHA_ACTUAL}. Si mencionas el ano en algun momento, usa el ano actual, no uno anterior.
{contexto_empresa}
Tu tarea es simular una entrevista laboral real para el puesto de {puesto} nivel {nivel}.

REGLA MAS IMPORTANTE: Tenes exactamente {max_preguntas} preguntas para hacer en total. Ni una mas. Cuando el candidato responda la pregunta numero {max_preguntas}, cerras la entrevista amablemente y escribis exactamente: ENTREVISTA_FINALIZADA

INSTRUCCIONES:
- Hace UNA sola pregunta por vez. Nunca hagas varias preguntas juntas.
- No hagas preguntas de seguimiento — cada pregunta cuenta para el total.
- Lleva la cuenta interna de cuantas preguntas hiciste.
- Al llegar a {max_preguntas} preguntas respondidas, cerra la entrevista inmediatamente.
- Hablas en espanol argentino, de manera natural y profesional.
- No reveles que sos una IA a menos que te lo pregunten directamente.

ESTRUCTURA DE {max_preguntas} PREGUNTAS:
1. Presentacion ("Contame sobre vos")
2. Experiencia laboral mas relevante
3. Pregunta tecnica especifica del puesto
4. Situacion dificil que hayas manejado
5. Motivacion y expectativas para {"esta empresa" if empresa else "este puesto"}{"" if max_preguntas == 5 else """
6. Trabajo en equipo o liderazgo
7. Pregunta tecnica avanzada
8. Cierre (tenes preguntas para nosotros?)"""}

Empeza la entrevista de forma natural y amigable."""

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
    try:
        if not request.nombre or not request.email:
            raise HTTPException(status_code=400, detail="Nombre y email son requeridos")

        sheets_ok = guardar_registro(request.nombre, request.email, request.situacion)
        email_ok = enviar_bienvenida(request.nombre, request.email)

        return {
            "ok": True,
            "sheets": sheets_ok,
            "email": email_ok,
            "mensaje": f"Bienvenido/a {request.nombre}! Revisa tu email."
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
            messages=[{"role": "user", "content": "Inicia la entrevista"}]
        )
        mensaje_ia = response.content[0].text
        return {
            "mensaje": mensaje_ia,
            "finalizada": False,
            "historial": [
                {"role": "user", "content": "Inicia la entrevista"},
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

        prompt = f"""Analiza esta entrevista para el puesto de {request.puesto} y genera feedback detallado y constructivo.

La fecha actual es {FECHA_ACTUAL}. Si mencionas el ano, usa el ano actual.

TRANSCRIPCION:
{historial_texto}

## Evaluacion general
[Puntaje del 1 al 10 con justificacion]

## Puntos fuertes
[3 puntos concretos con ejemplos]

## Areas de mejora
[3 puntos concretos con ejemplos y como reformularlos]

## Respuestas destacadas
[La mejor respuesta y por que fue efectiva]

## Consejos para proximas entrevistas
[3 consejos practicos para el mercado argentino]

## Proximos pasos recomendados
[Que deberia hacer esta semana]

Importante: no penalices respuestas genericas por falta de contexto sobre la empresa. Se honesto, constructivo y especifico."""

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

        prompt = f"""Analiza este CV para el puesto de {puesto} en el mercado argentino.

La fecha actual es {FECHA_ACTUAL}. Si mencionas el ano, usa el ano actual.

CV:
{texto_cv}

## Puntaje general
[Del 1 al 10 con justificacion]

## Fortalezas del CV
[3 puntos concretos]

## Mejoras urgentes
[3 cambios concretos a hacer YA]

## Palabras clave faltantes
[Keywords importantes que no aparecen]

## Seccion mas debil
[Cual es y como mejorarla]

## Recomendacion final
[El consejo mas importante]

Se especifico y orientado al mercado de datos en Argentina."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
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
            raise HTTPException(status_code=400, detail="El perfil no puede estar vacio")

        prompt = f"""Analiza este perfil de LinkedIn para alguien que busca trabajo como {puesto_objetivo} en el mercado argentino.

La fecha actual es {FECHA_ACTUAL}. Si mencionas el ano, usa el ano actual, no uno anterior.

PERFIL:
{perfil_texto}

## Puntaje general
[Del 1 al 10 con justificacion]

## Titulo profesional
[Evalua el actual y sugeri uno mejor optimizado para busquedas]

## Resumen (About)
[Evalua el actual y escribi uno mejorado listo para copiar y pegar]

## Experiencia laboral
[3 sugerencias concretas para mejorar como esta presentada]

## Palabras clave faltantes
[Keywords que los reclutadores buscan y no aparecen]

## Visibilidad en busquedas
[Consejos especificos para aparecer mas en busquedas]

## Recomendacion principal
[El cambio mas importante a hacer hoy]

Se especifico y orientado al mercado argentino de datos y tecnologia."""

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

        prompt = f"""Analiza este perfil de LinkedIn exportado como PDF para alguien que busca trabajo como {puesto_objetivo} en el mercado argentino.

La fecha actual es {FECHA_ACTUAL}. Si mencionas el ano, usa el ano actual, no uno anterior.

PERFIL:
{texto}

## Puntaje general
[Del 1 al 10 con justificacion]

## Titulo profesional
[Evalua el actual y sugeri uno mejor]

## Resumen (About)
[Evalua el actual y escribi uno mejorado listo para copiar]

## Experiencia laboral
[3 sugerencias concretas]

## Palabras clave faltantes
[Keywords importantes que no aparecen]

## Visibilidad en busquedas
[Consejos para aparecer mas en busquedas]

## Recomendacion principal
[El cambio mas importante hoy]

Se especifico y orientado al mercado argentino."""

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
