"""Cliente del modelo y estado interno de cada conversación autenticada."""
import os
from dataclasses import dataclass, field
from openai import OpenAI

MODELO = "modelo-clase"

def crear_cliente_llm() -> OpenAI:
    """Crea el cliente usando únicamente los secretos de Codespaces."""
    faltan = [v for v in ("LLM_API_KEY", "LLM_BASE_URL") if not os.environ.get(v)]
    if faltan:
        raise RuntimeError(f"Faltan los secretos {', '.join(faltan)}. Revisa la sección 2 de GUIA.md.")
    return OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])

@dataclass
class Sesion:
    """Estado de cliente y controles de seguridad, invisible para el modelo."""
    cliente_id: str
    turnos: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    mensaje_actual: str = ""
    accion_pendiente: tuple[str, str, int | None] | None = None
    confirmacion_validada: tuple[str, str, int | None] | None = None
    intentos_por_pedido: dict[str, int] = field(default_factory=dict)
