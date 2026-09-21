from flask import Blueprint, jsonify, render_template, request

from app.models.Flota import Flota
from app.models.Sucursal import Sucursal
from app.services import validadores as v
from app.services.tarifas import tarifa_vigente

home_bp = Blueprint('home', __name__)


@home_bp.route('/')
def index():
    return render_template('index.html')


@home_bp.route('/api/sedes')
def listar_sedes():
    sedes = Sucursal.query.filter_by(estado='activa').order_by(Sucursal.nombre).all()
    return jsonify([
        {'id_sucursal': s.id_sucursal, 'nombre': s.nombre, 'direccion': s.direccion}
        for s in sedes
    ])


@home_bp.route('/api/flota')
def listar_flota():
    """Flota de las sedes activas, con el precio y minutos por bloque de la tarifa."""
    tarifa = tarifa_vigente()
    consulta = (Flota.query.join(Sucursal).filter(Sucursal.estado == 'activa', Flota.estado != 'inactivo'))
    if request.args.get('id_sucursal'):
        consulta = consulta.filter(Flota.id_sucursal == v.entero(request.args['id_sucursal'], 'sede', 1, 10**9))
    if request.args.get('tipo'):
        consulta = consulta.filter(Flota.tipo == request.args['tipo'][:30])
    return jsonify([
        {
            'id_flota': f.id_flota, 'nombre': f.nombre, 'tipo': f.tipo, 'modelo': f.modelo,
            'estado': f.estado, 'id_sucursal': f.id_sucursal,
            'precio': float(tarifa.precio), 'minutos': tarifa.minutos,
        }
        for f in consulta.order_by(Flota.id_flota).all()
    ])
