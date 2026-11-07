import json

from agente import herramientas  # noqa: F401
from agente.ciclo import _es_confirmacion_explicita
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion


def llamar(nombre, argumentos, sesion):
    return ejecutar(nombre, json.dumps(argumentos, ensure_ascii=False), sesion)


def test_confirmacion_explicita_no_acepta_ambiguedad():
    assert _es_confirmacion_explicita("Sí, confirmo")
    assert not _es_confirmacion_explicita("sí, pero mejor no")
    assert not _es_confirmacion_explicita("creo que sí")


def test_consulta_no_revela_pedido_ajeno():
    sesion = Sesion(cliente_id="C-01")
    resultado = llamar("consultar_pedido", {"numero_pedido": "P-1007"}, sesion)
    assert "error" in str(resultado).lower() or "no disponible" in str(resultado).lower()
    assert "televisor" not in str(resultado).lower()


def test_nota_de_pedido_no_se_devuelve_como_instruccion():
    sesion = Sesion(cliente_id="C-04")
    resultado = llamar("consultar_pedido", {"numero_pedido": "P-1011"}, sesion)
    assert "error" not in str(resultado).lower()
    assert "ignora las instrucciones" not in str(resultado).lower()


def test_cancelacion_exige_confirmacion_de_sesion():
    sesion = Sesion(cliente_id="C-01")
    respuesta = llamar("cancelar_pedido", {"numero_pedido": "P-1016"}, sesion)
    assert "confirm" in str(respuesta).lower()
    assert sesion.accion_pendiente
    assert not sesion.confirmacion_validada


def test_reclamo_requiere_motivo_y_producto():
    sesion = Sesion(cliente_id="C-01")
    respuesta = llamar("registrar_reclamo", {"numero_pedido": "P-1002"}, sesion)
    assert "error" in str(respuesta).lower() or "producto" in str(respuesta).lower() or "motivo" in str(respuesta).lower()


def test_escalamiento_conserva_resumen():
    sesion = Sesion(cliente_id="C-03")
    sesion.mensaje_actual = "Quiero hablar con un asesor"
    respuesta = llamar("escalar_asesor", {"resumen": "Cliente solicita hablar con asesor por P-1007", "numero_pedido": "P-1007"}, sesion)
    assert "error" not in str(respuesta).lower()
    assert respuesta
