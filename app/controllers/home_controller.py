from flask import (
    Blueprint,
    jsonify,
    render_template,
    request
)

from app.models.Flota import Flota
from app.models.Sucursal import Sucursal


home_bp = Blueprint(
    'home',
    __name__
)


@home_bp.route('/')
def index():
    return render_template(
        'index.html'
    )


@home_bp.route('/api/sedes')
def listar_sedes():

    sedes = Sucursal.query.filter_by(
        estado='activa'
    ).all()

    return jsonify([
        {
            'id_sucursal': s.id_sucursal,
            'nombre': s.nombre,
            'direccion': s.direccion
        }
        for s in sedes
    ])


@home_bp.route('/api/flota')
def listar_flota():

    consulta = Flota.query

    if request.args.get('id_sucursal'):
        consulta = consulta.filter_by(
            id_sucursal=request.args['id_sucursal']
        )

    if request.args.get('tipo'):
        consulta = consulta.filter_by(
            tipo=request.args['tipo']
        )

    return jsonify([
        {
            'id_flota': f.id_flota,
            'nombre': f.nombre,
            'tipo': f.tipo,
            'modelo': f.modelo,
            'estado': f.estado,
            'precio_hora': float(
                f.precio_hora or 0
            ),
            'id_sucursal': f.id_sucursal
        }
        for f in consulta.all()
    ])
