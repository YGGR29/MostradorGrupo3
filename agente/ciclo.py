"""Ciclo de conversación, herramientas y confirmación de acciones."""
import json
import re
import unicodedata
from pathlib import Path
from agente import herramientas  # noqa: F401
from agente.herramientas.registro import ejecutar, esquemas
from agente.sesion import MODELO, Sesion, crear_cliente_llm

MAX_ITERACIONES = 8
INSTRUCCIONES = Path(__file__).parent / "instrucciones.md"
_cliente_llm = None

def _instrucciones() -> str:
    texto = INSTRUCCIONES.read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", texto, flags=re.S).strip()

def _como_json(texto: str):
    try:
        return json.loads(texto or "{}")
    except ValueError:
        return texto

def _es_confirmacion_explicita(texto: str) -> bool:
    normalizado = unicodedata.normalize("NFD", texto.casefold())
    normalizado = "".join(c for c in normalizado if unicodedata.category(c) != "Mn")
    limpio = " ".join("".join(c if c.isalnum() or c.isspace() else " " for c in normalizado).split())
    palabras = set(limpio.split())
    if palabras & {"no", "pero", "espera", "cambio", "cambiar"}:
        return False
    exactas = {"si", "yes", "confirmo", "autorizo", "acepto", "procede", "hazlo", "adelante", "si confirmo", "si autorizo", "si acepto", "yes confirm", "i confirm"}
    prefijos = ("si confirmo ", "si autorizo ", "si acepto ", "yes confirm ", "i confirm ")
    return limpio in exactas or limpio.startswith(prefijos)

def _preparar_confirmacion(sesion: Sesion, mensaje: str) -> None:
    pendiente = sesion.accion_pendiente
    sesion.confirmacion_validada = None
    if pendiente is None:
        return
    if _es_confirmacion_explicita(mensaje):
        sesion.confirmacion_validada = pendiente
    else:
        # Solo una respuesta afirmativa e inmediata puede aprobar la acción pendiente.
        sesion.accion_pendiente = None

def responder(sesion: Sesion, historial: list[dict], mensaje: str) -> tuple[str, list[dict]]:
    """Procesa un turno y devuelve la respuesta junto con la traza de herramientas."""
    global _cliente_llm
    _cliente_llm = _cliente_llm or crear_cliente_llm()
    _preparar_confirmacion(sesion, mensaje)
    sesion.mensaje_actual = mensaje
    sesion.turnos += 1
    historial.append({"role": "user", "content": mensaje})
    traza = []
    for _ in range(MAX_ITERACIONES):
        instrucciones = _instrucciones()
        sistema = [{"role": "system", "content": instrucciones}] if instrucciones else []
        respuesta = _cliente_llm.chat.completions.create(model=MODELO, messages=sistema + historial, tools=esquemas() or None)
        sesion.tokens_entrada += respuesta.usage.prompt_tokens
        sesion.tokens_salida += respuesta.usage.completion_tokens
        mensaje_modelo = respuesta.choices[0].message
        historial.append(mensaje_modelo.model_dump(exclude_none=True))
        if not mensaje_modelo.tool_calls:
            return mensaje_modelo.content or "", traza
        for llamada in mensaje_modelo.tool_calls:
            resultado = ejecutar(llamada.function.name, llamada.function.arguments, sesion)
            traza.append({"herramienta": llamada.function.name, "argumentos": _como_json(llamada.function.arguments), "resultado": resultado})
            historial.append({"role": "tool", "tool_call_id": llamada.id, "content": json.dumps(resultado, ensure_ascii=False, default=str)})
    return "Lo siento, no pude completar tu solicitud. Intenta de nuevo con otras palabras.", traza
