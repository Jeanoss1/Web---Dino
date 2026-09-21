import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.services.errores import ErrorNegocio

_CORREO = re.compile(r'^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$')
_DNI = re.compile(r'^\d{8}$')
_CE = re.compile(r'^[A-Za-z0-9]{9,12}$')
_TELEFONO = re.compile(r'^\d{9}$')


def texto(valor, campo, minimo=1, maximo=100):
    valor = (valor or '').strip()
    if len(valor) < minimo:
        raise ErrorNegocio(f'Completa el campo «{campo}».')
    if len(valor) > maximo:
        raise ErrorNegocio(f'«{campo}» admite como máximo {maximo} caracteres.')
    return valor


def correo(valor):
    valor = (valor or '').strip().lower()
    if len(valor) > 120 or not _CORREO.match(valor):
        raise ErrorNegocio('Ingresa un correo válido.')
    return valor


def documento(valor):
    valor = (valor or '').strip()
    if not (_DNI.match(valor) or _CE.match(valor)):
        raise ErrorNegocio('El documento debe tener 8 dígitos (DNI) o de 9 a 12 caracteres (carné).')
    return valor


def telefono(valor):
    valor = (valor or '').strip().replace(' ', '')
    if valor.startswith('+51'):
        valor = valor[3:]
    if not _TELEFONO.match(valor):
        raise ErrorNegocio('El teléfono debe tener 9 dígitos.')
    return valor


def contrasena(valor):
    valor = valor or ''
    if len(valor) < 8 or not re.search(r'[A-Za-z]', valor) or not re.search(r'\d', valor):
        raise ErrorNegocio('La contraseña debe tener al menos 8 caracteres, con letras y números.')
    if len(valor) > 128:
        raise ErrorNegocio('La contraseña es demasiado larga.')
    return valor


def entero(valor, campo, minimo=1, maximo=1000):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ErrorNegocio(f'«{campo}» debe ser un número entero.')
    if not minimo <= numero <= maximo:
        raise ErrorNegocio(f'«{campo}» debe estar entre {minimo} y {maximo}.')
    return numero


def dinero(valor, campo, minimo=Decimal('0'), maximo=Decimal('100000'), permitir_cero=True):
    try:
        monto = Decimal(str(valor).replace(',', '.').strip())
    except (InvalidOperation, AttributeError):
        raise ErrorNegocio(f'«{campo}» no es un monto válido.')
    if not monto.is_finite() or monto < minimo or monto > maximo or (monto == 0 and not permitir_cero):
        raise ErrorNegocio(f'«{campo}» no es un monto válido.')
    return monto.quantize(Decimal('0.01'))


def fecha(valor, campo='fecha'):
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    try:
        return datetime.strptime((valor or '').strip(), '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        raise ErrorNegocio(f'La {campo} debe tener el formato AAAA-MM-DD.')
