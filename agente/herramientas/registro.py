"""Registro y despacho uniforme de herramientas del agente."""
import inspect
import json
from typing import Callable
from pydantic import BaseModel, ValidationError
from agente.sesion import Sesion

HERRAMIENTAS: dict[str, tuple[Callable, type[BaseModel]]] = {}

class ErrorDeHerramienta(Exception):
    """La herramienta no puede hacer lo solicitado; el error se devuelve al modelo."""

def herramienta(funcion: Callable) -> Callable:
    """Registra una función y su modelo Pydantic de argumentos."""
    modelo_args = inspect.signature(funcion).parameters["args"].annotation
    HERRAMIENTAS[funcion.__name__] = (funcion, modelo_args)
    return funcion

def esquemas() -> list[dict]:
    """Devuelve las herramientas en el formato de la API de chat."""
    return [{"type": "function", "function": {
        "name": nombre, "description": inspect.getdoc(funcion),
        "parameters": modelo_args.model_json_schema(),
    }} for nombre, (funcion, modelo_args) in HERRAMIENTAS.items()]

def ejecutar(nombre: str, argumentos_json: str, sesion: Sesion) -> dict:
    """Ejecuta una herramienta y devuelve errores controlados sin exponer excepciones."""
    if nombre not in HERRAMIENTAS:
        return {"error": f"No existe la herramienta '{nombre}'."}
    funcion, modelo_args = HERRAMIENTAS[nombre]
    try:
        args = modelo_args.model_validate_json(argumentos_json or "{}")
    except ValidationError as e:
        return {"error": "Argumentos inválidos.", "detalle": json.loads(e.json(include_url=False))}
    try:
        return funcion(sesion, args)
    except ErrorDeHerramienta as e:
        numero = getattr(args, "numero_pedido", None)
        if numero:
            sesion.intentos_por_pedido[numero] = sesion.intentos_por_pedido.get(numero, 0) + 1
        return {"error": str(e)}
    except Exception as e:
        return {"error": "Falla interna de la herramienta.", "detalle": f"{type(e).__name__}: {e}"}
