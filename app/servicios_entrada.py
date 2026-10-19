"""Regla de precio de los paquetes de entrada por tiempo (Hoyos Rubio y
sedes futuras del mismo modelo). La usan tanto la reserva online
(entrada_controller.crear_reserva_entrada) como la venta en caja
(entrada_controller.crear_venta_entrada), para no calcular el precio dos
veces ni confiar en lo que mande el cliente."""


class ErrorPaquete(Exception):
    pass


def calcular_subtotal_paquete(paquete, cantidad, nino_hasta_5=None):
    """Valida la cantidad contra el mínimo del paquete y devuelve el
    subtotal (ya multiplicado si el paquete es por niño/adulto).

    `nino_hasta_5` solo aplica al Pack Guía: el acompañante adulto solo paga
    la tarifa reducida si el niño que acompaña tiene hasta 5 años; si no,
    debe comprarle la entrada individual regular en su lugar.
    """

    if cantidad is None or cantidad < 1:
        raise ErrorPaquete('La cantidad debe ser al menos 1')

    if paquete.tipo == 'pack_guia' and not nino_hasta_5:
        raise ErrorPaquete(
            'El Pack Guía (acompañante adulto) solo aplica para niños de '
            'hasta 5 años. Si el niño es mayor, el adulto paga la entrada '
            'individual regular.'
        )

    minimo = paquete.minimo_cantidad or 1

    if cantidad < minimo:
        raise ErrorPaquete(
            f'{paquete.nombre} requiere un mínimo de {minimo} '
            f'{"niños" if paquete.es_por_ninio else "unidades"}'
        )

    if paquete.es_por_ninio:
        return paquete.precio * cantidad

    return paquete.precio
