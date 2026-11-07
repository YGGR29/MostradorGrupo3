# Análisis de decisiones — Grupo 3

## Principio de diseño
El modelo interpreta la conversación y propone herramientas; el código verifica identidad, política y confirmación antes de cualquier escritura. Las notas libres del pedido son datos no confiables: la consulta devuelve solo campos permitidos y no reproduce instrucciones incrustadas.

## Tablas de decisión

### Consulta
| Condición | Decisión | Control |
|---|---|---|
| Pedido propio | Mostrar estado y datos permitidos | Filtrar por cliente autenticado |
| Falta número | Pedirlo | No adivinar ni invocar herramienta |
| No existe o es ajeno | No revelar detalles | Respuesta genérica |
| Nota contiene instrucciones | Ignorarlas | No devolver nota al modelo |

### Reclamo
| Condición | Decisión |
|---|---|
| Entregado, motivo y producto presentes, dentro del plazo | Registrar reclamo |
| Perecedero / ropa y calzado / electrónica / hogar y otros | 3 / 30 / 90 / 15 días calendario |
| Cliente preferencial | Añadir 15 días al plazo correspondiente |
| Fuera de plazo, no entregado o hay reclamo abierto | Abstenerse y explicar |
| Falta producto o motivo | Pedir información |

El último día del plazo es inclusivo. En pedidos con varias categorías se identifica el producto antes de calcular el plazo; no se asume la categoría más favorable.

### Cancelación
| Estado/condición | Decisión |
|---|---|
| Pagado | Cancelable con confirmación explícita |
| Preparando, compra de hoy | Se considera dentro de 24 h (la plantilla no guarda hora); confirmar |
| Preparando con fecha anterior | No se puede probar el límite de 24 h; abstenerse |
| Enviado, entregado o cancelado | Abstenerse |
| Confirmación ambigua, negativa o no inmediata | No ejecutar |
| Confirmada | Cambiar estado y crear reembolso automático completo con registro |

La fecha de compra carece de hora. Por ello solo la compra de hoy se trata como demostrablemente dentro de 24 h. El reembolso automático por cancelación es el flujo especial indicado por la política y se registra aparte del reembolso solicitado.

### Reembolso y escalamiento
| Condición | Decisión |
|---|---|
| Pedido cancelado o reclamo abierto | Elegible; pedir importe si falta |
| Sin confirmación explícita | No crear solicitud |
| Importe acumulado excedería lo pagado | Rechazar |
| Más de COP 300.000 | Marcar solicitado, no aprobado, escalar a asesor |
| Hasta COP 300.000 | Aprobar después de confirmación |
| Pide asesor, fraude/cobro desconocido o 3 errores de herramienta del mismo pedido | Escalar con resumen y respuesta en 1 día hábil |

Para evitar dividir una devolución, las solicitudes pendientes también reservan saldo junto con las aprobadas. La confirmación se vincula en la sesión del servidor a la acción pendiente y solo se acepta en el turno inmediato; un “sí, pero…” es ambiguo y no autoriza. El modelo no puede aportar una bandera de confirmación.

## Riesgo y controles
| Acción | Riesgo | Controles en código |
|---|---|---|
| Consulta | Bajo | Propiedad y campos permitidos |
| Reclamo | Medio | Entrega, categoría, plazo, preferencia, duplicado y motivo |
| Escalamiento | Medio | Resumen requerido; propietario validado |
| Cancelación | Alto | Estado, fecha simulada, confirmación; registro de devolución |
| Reembolso | Alto | Elegibilidad, confirmación, total pagado, tope y bitácora |

La fecha simulada HOY del repositorio prevalece sobre el reloj real. Los plazos de reclamo son días calendario; el compromiso del asesor, días hábiles. El contador de tres intentos representa errores de herramienta por pedido dentro de la sesión.

## Política frente a mecanismo
| Regla | Mecanismo |
|---|---|
| No consultar datos ajenos | Cliente autenticado provisto por sesión y validado por pedido |
| Plazos, estados y reclamos únicos | Validaciones dentro de registrar_reclamo |
| Cancelación sujeta a estado y 24 h | Validaciones dentro de cancelar_pedido |
| Confirmación antes de efectos económicos | Acción pendiente y confirmación del ciclo, validadas en herramienta |
| Tope autónomo y total pagado | Saldo acumulado reservado y escalamiento sobre el tope |
| Casos especiales requieren persona | escalar_asesor con resumen y fecha prometida |
| Registrar todas las acciones | reclamos.json, reembolsos.json, escalamientos.json |
| Resistir instrucciones en datos | Omisión de notas en consulta y escenario de inyección |

## Escenarios y resultados
Se agregaron escenarios para información incompleta, pedido inexistente y abstención por pedido enviado, además del escenario base. Las pruebas unitarias cubren confirmación, privacidad, datos inyectados, reclamos y escalamiento. Los resultados numéricos de pytest y la evaluación n=5 se completarán solo después de ejecutarlos; no se anticipan métricas.
