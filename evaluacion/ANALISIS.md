# Análisis de decisiones — Grupo 3

## Alcance y principio de diseño

El modelo interpreta la conversación y propone llamadas. Las herramientas son la autoridad: verifican identidad, estado, fechas, saldo, confirmación y límites antes de escribir. Las instrucciones del agente ayudan a pedir datos y explicar resultados, pero no sustituyen validaciones. Las notas libres del cliente se tratan como datos no confiables y no se incorporan a las respuestas al consultar un pedido.

## Tablas de decisión

### Consultar

| Situación | Decisión | Mecanismo |
|---|---|---|
| Pedido propio de la sesión | Mostrar estado, fecha y productos | consultar_pedido filtra por id_cliente autenticado |
| Falta número de pedido | Pedirlo; no adivinar | Esquema y respuesta de herramienta |
| No existe o pertenece a otro cliente | No revelar datos | Respuesta genérica de no disponible |
| Pedido contiene texto con órdenes | Ignorar ese contenido | La herramienta devuelve campos permitidos, omite notas |

### Reclamos

| Situación | Decisión | Mecanismo |
|---|---|---|
| Entregado, dentro del plazo | Registrar motivo y producto | Validación en herramienta |
| Sin producto o motivo | Pedir el dato | No se escribe reclamo incompleto |
| Producto perecedero | Hasta 3 días calendario desde entrega | Diferencia de fechas con HOY |
| Ropa/calzado, electrónica, hogar/otro | 30, 90, 15 días respectivamente | Tabla de categorías en código |
| Preferencial | Plazo aplicable + 15 días | Solo si el registro del cliente confirma preferencia |
| No entregado, fuera de plazo o reclamo abierto | Abstenerse; explicar | Validaciones previas a escritura; no se duplica reclamo abierto |

El límite se considera inclusivo: el día exacto del plazo todavía admite reclamo. En pedidos con varias categorías se debe identificar el producto antes de aplicar el plazo. No se extrapola el plazo de un artículo al resto.

### Cancelación

| Estado/condición | Decisión |
|---|---|
| Pagado | Puede cancelarse, con confirmación explícita |
| Preparando y compra de hoy (fecha disponible, sin hora) | Se admite como dentro de 24 h; solicitar confirmación |
| Preparando con compra anterior | Abstenerse: no hay hora fiable para probar las 24 h |
| Enviado, entregado o cancelado | Abstenerse |
| Confirmación no inmediata o ambigua | No ejecutar; pedir aclaración |
| Cancelación confirmada | Cancelar y crear reembolso automático íntegro con trazabilidad |

La plantilla solo guarda fechas, no horas. Para no inventar una hora de compra, se interpreta “compra de hoy” como el único caso comprobable dentro de las 24 horas simuladas; si es de un día anterior, no se cancela desde esta automatización. La política establece que una cancelación aprobada genera automáticamente el reembolso completo, por lo que este flujo específico registra el reembolso automático, aunque supere el umbral autónomo de reembolsos ordinarios. Se registra separado del flujo de solicitud de reembolso.

### Reembolsos

| Situación | Decisión |
|---|---|
| Pedido cancelado o reclamo abierto | Elegible, sujeto a confirmación |
| Importe ausente | Pedir importe; nunca inferirlo |
| Total acumulado superior al pagado | Rechazar |
| Total acumulado supera COP 300.000 | No aprobar autónomamente; dejar solicitado y escalar |
| Dentro del tope | Confirmación explícita en el turno siguiente y luego registro aprobado |
| Cliente pide asesor, fraude/cobro desconocido o 3 errores de herramienta | Escalar con resumen y plazo de respuesta de 1 día hábil |

Los importes ya aprobados y los solicitados cuentan como saldo reservado para prevenir que varios intentos excedan lo pagado. La solicitud por encima del tope no afirma que ya se haya pagado o aprobado: queda solicitado y se deriva al asesor.

## Confirmación y ambigüedades

La confirmación se liga a la acción pendiente guardada en Sesion, no a argumentos que entregue el modelo. Solo se acepta una respuesta afirmativa inequívoca en el turno inmediato; frases como “sí, pero…” no ejecutan la acción. Una respuesta negativa o una nueva solicitud limpia la confirmación pendiente. Las herramientas requieren que el ciclo marque la confirmación validada antes de modificar pedido o dinero.

La fecha simulada del repositorio (HOY) se usa en reglas de plazo; no se reemplaza con la fecha real del equipo. Los plazos son días calendario excepto el compromiso del asesor, que se comunica en días hábiles. La escalación por tres intentos cuenta fallos de herramientas vinculados al mismo pedido durante la sesión; no pretende medir todas las vueltas del diálogo.

## Clasificación de riesgo

| Acción | Riesgo | Razón |
|---|---|---|
| Consulta | Bajo | Solo lectura y restringida por cliente |
| Reclamo | Medio | Crea un registro que debe reflejar fielmente el motivo |
| Escalamiento | Medio | Crea un caso y plazo de contacto |
| Cancelación | Alto | Cambia estado y registra salida de dinero |
| Reembolso | Alto | Impacto monetario directo; tope acumulado y confirmación obligatorios |

## Política y mecanismo

| Política | Control ejecutable |
|---|---|
| No acceder a pedido ajeno | id_cliente proviene de sesión y se comprueba en cada herramienta |
| Reclamo solo entregado y dentro de plazo | Estados, categoría, fecha, preferencia, producto y duplicados se validan en herramienta |
| Cancelar solo estados permitidos y en 24 h si preparando | Verificación de estado/fecha en cancelar_pedido |
| Confirmación antes de cancelar o pedir reembolso | Estado pendiente del servidor y comprobación por herramienta |
| Tope COP 300.000 y no exceder total | Suma acumulada comprobada antes de guardar; importes altos escalan |
| Escalar casos especiales | Herramienta valida petición, señales de fraude y contador de fallos |
| Datos no confiables no son órdenes | Notas no se devuelven como instrucciones al modelo; prompts en datos se evalúan |
| Dejar trazabilidad | Escritura en reclamos.json, reembolsos.json, escalamientos.json |

## Pruebas y resultados

Se añadieron escenarios para consulta normal, falta de información, pedido inexistente, abstención por política, pedido ajeno, inyección en datos y reembolso sobre el tope; el escenario de confirmación de cancelación prueba el flujo de dos turnos. Las pruebas automatizadas verifican límites directamente en las herramientas. Los resultados de pytest y de la evaluación con el modelo se consignarán después de ejecutarlos con el presupuesto autorizado del grupo; no se reportan cifras no medidas.
