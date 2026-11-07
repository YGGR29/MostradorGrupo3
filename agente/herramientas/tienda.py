"""Herramientas de soporte con reglas de negocio aplicadas en código."""
import re
import unicodedata
from pydantic import BaseModel, Field
from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio

TOPE_REEMBOLSO = 300_000
_PLAZOS = {"perecedero": 3, "ropa": 30, "electronica": 90, "hogar": 15}

def _normalizar(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")

def _pedido_cliente(sesion: Sesion, numero: str):
    pedido = next((p for p in repositorio.leer_pedidos() if p.numero == numero), None)
    if pedido is None or pedido.cliente_id != sesion.cliente_id:
        raise ErrorDeHerramienta("No encontré un pedido con ese número asociado a tu cuenta.")
    return pedido

def _resumen_pedido(pedido) -> dict:
    # La nota del pedido se omite: es texto no confiable y no es necesario para atender.
    return {"numero": pedido.numero, "estado": pedido.estado,
            "fecha_compra": pedido.fecha_compra.isoformat(),
            "fecha_entrega": pedido.fecha_entrega.isoformat() if pedido.fecha_entrega else None,
            "productos": [{"nombre": p.nombre, "categoria": p.categoria, "cantidad": p.cantidad} for p in pedido.productos],
            "total": pedido.total}

def _siguiente_id(prefijo: str, filas: list) -> str:
    numeros = [int(f.id.rsplit("-", 1)[1]) for f in filas if f.id.rsplit("-", 1)[-1].isdigit()]
    return f"{prefijo}-{max(numeros, default=0) + 1:03d}"

def _confirmar(sesion: Sesion, clave: tuple[str, str, int | None], detalle: str) -> None:
    if sesion.confirmacion_validada == clave:
        sesion.confirmacion_validada = None
        sesion.accion_pendiente = None
        return
    if sesion.accion_pendiente is not None and sesion.accion_pendiente != clave:
        raise ErrorDeHerramienta("Hay otra acción esperando confirmación. No ejecuté esta solicitud; confirma o rechaza la acción pendiente primero.")
    sesion.accion_pendiente = clave
    raise ErrorDeHerramienta(f"Antes de continuar, confirma explícitamente: {detalle}. Responde Sí, confirmo, o No.")

def _registrar_escalamiento(sesion: Sesion, motivo: str, resumen: str, numero_pedido: str | None = None) -> dict:
    filas = repositorio.leer_escalamientos()
    registro = repositorio.Escalamiento(id=_siguiente_id("ES", filas), cliente_id=sesion.cliente_id,
        numero_pedido=numero_pedido, fecha=repositorio.HOY, motivo=motivo, resumen=resumen.strip()[:500])
    filas.append(registro)
    repositorio.guardar_escalamientos(filas)
    return {"id": registro.id, "motivo": motivo, "plazo_contacto": "un día hábil"}

class ArgsConsultarPedido(BaseModel):
    numero_pedido: str | None = Field(default=None, description="Número del pedido. Omítelo para listar los pedidos propios del cliente.")

@herramienta
def consultar_pedido(sesion: Sesion, args: ArgsConsultarPedido) -> dict:
    """Consulta el estado y los datos básicos de los pedidos del cliente autenticado."""
    propios = [p for p in repositorio.leer_pedidos() if p.cliente_id == sesion.cliente_id]
    if args.numero_pedido:
        pedido = next((p for p in propios if p.numero == args.numero_pedido), None)
        if pedido is None:
            raise ErrorDeHerramienta("No encontré un pedido con ese número asociado a tu cuenta.")
        return {"pedido": _resumen_pedido(pedido)}
    return {"pedidos": [_resumen_pedido(p) for p in propios]}

class ArgsRegistrarReclamo(BaseModel):
    numero_pedido: str = Field(description="Número del pedido entregado.")
    producto: str = Field(description="Nombre del producto afectado, tal como lo indica el cliente.")
    motivo: str = Field(description="Motivo del reclamo, en palabras del cliente.")

@herramienta
def registrar_reclamo(sesion: Sesion, args: ArgsRegistrarReclamo) -> dict:
    """Registra un reclamo procedente dentro del plazo, con producto y motivo informados."""
    pedido = _pedido_cliente(sesion, args.numero_pedido)
    if pedido.estado != "entregado" or pedido.fecha_entrega is None:
        raise ErrorDeHerramienta("Solo se puede reclamar sobre un pedido que figure como entregado.")
    motivo = args.motivo.strip()
    if not motivo:
        raise ErrorDeHerramienta("Necesito el motivo del reclamo tal como lo describe el cliente.")
    producto = next((p for p in pedido.productos if _normalizar(p.nombre) == _normalizar(args.producto.strip())), None)
    if producto is None:
        nombres = ", ".join(p.nombre for p in pedido.productos)
        raise ErrorDeHerramienta(f"Indica cuál producto de este pedido presenta el problema. Productos: {nombres}.")
    abiertos = [r for r in repositorio.leer_reclamos() if r.numero_pedido == pedido.numero and r.estado == "abierto"]
    if abiertos:
        return {"reclamo_existente": True, "id": abiertos[0].id, "estado": abiertos[0].estado}
    cliente = next(c for c in repositorio.leer_clientes() if c.id == sesion.cliente_id)
    limite = _PLAZOS[producto.categoria] + (15 if cliente.categoria == "preferente" else 0)
    dias = (repositorio.HOY - pedido.fecha_entrega).days
    if dias < 0 or dias > limite:
        raise ErrorDeHerramienta(f"El plazo para reclamar venció. El límite aplicable es {limite} días calendario desde la entrega.")
    reclamos = repositorio.leer_reclamos()
    reclamo = repositorio.Reclamo(id=_siguiente_id("RC", reclamos), numero_pedido=pedido.numero,
        cliente_id=sesion.cliente_id, fecha=repositorio.HOY, motivo=motivo, estado="abierto")
    reclamos.append(reclamo)
    repositorio.guardar_reclamos(reclamos)
    sesion.intentos_por_pedido.pop(pedido.numero, None)
    return {"id": reclamo.id, "numero_pedido": pedido.numero, "estado": reclamo.estado,
            "dias_transcurridos": dias, "plazo_aplicable": limite}

class ArgsCancelarPedido(BaseModel):
    numero_pedido: str = Field(description="Número del pedido que el cliente desea cancelar.")

@herramienta
def cancelar_pedido(sesion: Sesion, args: ArgsCancelarPedido) -> dict:
    """Cancela un pedido propio solo si la política lo permite y el cliente lo confirmó."""
    pedido = _pedido_cliente(sesion, args.numero_pedido)
    if pedido.estado == "pagado":
        pass
    elif pedido.estado == "en_preparacion":
        horas = (repositorio.HOY - pedido.fecha_compra).days * 24
        if horas < 0 or horas >= 24:
            raise ErrorDeHerramienta("Un pedido en preparación solo se puede cancelar durante las primeras 24 horas desde la compra.")
    else:
        raise ErrorDeHerramienta(f"No se puede cancelar un pedido en estado {pedido.estado}.")
    reembolsos = repositorio.leer_reembolsos()
    if any(r.numero_pedido == pedido.numero and r.estado in ("aprobado", "solicitado") for r in reembolsos):
        raise ErrorDeHerramienta("Este pedido ya tiene un reembolso registrado; no puedo crear otro.")
    detalle = f"cancelar el pedido {pedido.numero}; genera un reembolso automático de COP {pedido.total:,}"
    _confirmar(sesion, ("cancelar", pedido.numero, None), detalle)
    pedidos = repositorio.leer_pedidos()
    next(p for p in pedidos if p.numero == pedido.numero).estado = "cancelado"
    repositorio.guardar_pedidos(pedidos)
    reembolsos.append(repositorio.Reembolso(id=_siguiente_id("RE", reembolsos), numero_pedido=pedido.numero,
        cliente_id=sesion.cliente_id, fecha=repositorio.HOY, monto=pedido.total,
        motivo="Reembolso automático por cancelación confirmada", estado="aprobado"))
    repositorio.guardar_reembolsos(reembolsos)
    sesion.intentos_por_pedido.pop(pedido.numero, None)
    return {"numero_pedido": pedido.numero, "estado": "cancelado", "reembolso_automatico": pedido.total}

class ArgsSolicitarReembolso(BaseModel):
    numero_pedido: str = Field(description="Número del pedido propio.")
    monto: int = Field(gt=0, description="Monto entero en pesos colombianos.")
    motivo: str = Field(description="Motivo del reembolso.")

@herramienta
def solicitar_reembolso(sesion: Sesion, args: ArgsSolicitarReembolso) -> dict:
    """Solicita un reembolso procedente, con confirmación, saldo y tope validados."""
    pedido = _pedido_cliente(sesion, args.numero_pedido)
    motivo = args.motivo.strip()
    if not motivo:
        raise ErrorDeHerramienta("Necesito el motivo del reembolso.")
    abierto = any(r.numero_pedido == pedido.numero and r.estado == "abierto" for r in repositorio.leer_reclamos())
    if pedido.estado != "cancelado" and not abierto:
        raise ErrorDeHerramienta("Un reembolso procede únicamente para un pedido cancelado o con un reclamo abierto.")
    reembolsos = repositorio.leer_reembolsos()
    registrado = sum(r.monto for r in reembolsos if r.numero_pedido == pedido.numero and r.estado in ("aprobado", "solicitado"))
    disponible = pedido.total - registrado
    if args.monto > disponible:
        raise ErrorDeHerramienta(f"El monto excede el saldo reembolsable de COP {max(disponible, 0):,} para este pedido.")
    detalle = f"solicitar un reembolso de COP {args.monto:,} para el pedido {pedido.numero}"
    _confirmar(sesion, ("reembolso", pedido.numero, args.monto), detalle)
    alto = args.monto > TOPE_REEMBOLSO
    reembolso = repositorio.Reembolso(id=_siguiente_id("RE", reembolsos), numero_pedido=pedido.numero,
        cliente_id=sesion.cliente_id, fecha=repositorio.HOY, monto=args.monto, motivo=motivo,
        estado="solicitado" if alto else "aprobado")
    reembolsos.append(reembolso)
    repositorio.guardar_reembolsos(reembolsos)
    resultado = {"id": reembolso.id, "numero_pedido": pedido.numero, "monto": args.monto, "estado": reembolso.estado}
    if alto:
        resultado["escalamiento"] = _registrar_escalamiento(sesion, "reembolso_supera_tope",
            f"Aprobación humana requerida para COP {args.monto:,}. Motivo: {motivo}", pedido.numero)
    sesion.intentos_por_pedido.pop(pedido.numero, None)
    return resultado

class ArgsEscalarAsesor(BaseModel):
    resumen: str = Field(description="Resumen breve y fiel del caso para el asesor.")
    numero_pedido: str | None = Field(default=None, description="Número del pedido relacionado, si existe.")

@herramienta
def escalar_asesor(sesion: Sesion, args: ArgsEscalarAsesor) -> dict:
    """Escala un caso solo cuando la política lo permite y registra el resumen para el asesor."""
    resumen = args.resumen.strip()
    if not resumen:
        raise ErrorDeHerramienta("El resumen del caso es obligatorio para el asesor.")
    if args.numero_pedido:
        _pedido_cliente(sesion, args.numero_pedido)
    mensaje = _normalizar(sesion.mensaje_actual)
    solicitud = any(p in mensaje for p in ("asesor", "humano", "representante", "persona real", "hablar con alguien"))
    fraude = any(p in mensaje for p in ("fraude", "no reconozco el cobro", "cobro no reconocido", "cargo no autorizado"))
    intentos = bool(args.numero_pedido and sesion.intentos_por_pedido.get(args.numero_pedido, 0) >= 3)
    if not (solicitud or fraude or intentos):
        raise ErrorDeHerramienta("La política no permite escalar sin solicitud del cliente, posible fraude o tres intentos fallidos.")
    motivo = "solicitud_cliente" if solicitud else "posible_fraude" if fraude else "sin_resolver_despues_de_tres_intentos"
    registro = _registrar_escalamiento(sesion, motivo, resumen, args.numero_pedido)
    if args.numero_pedido:
        sesion.intentos_por_pedido.pop(args.numero_pedido, None)
    return {"cliente_id": sesion.cliente_id, **registro}
