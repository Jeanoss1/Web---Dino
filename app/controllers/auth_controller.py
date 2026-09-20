from flask import Blueprint, render_template

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/registro')
def registro():
    return render_template('registro.html')

@auth_bp.route('/iniciar-sesion')
def iniciar_sesion():
    return render_template('iniciar_sesion.html')