from flask import Blueprint, render_template

home_bp = Blueprint('home', __name__)


@home_bp.route('/')
def index():
    return render_template('index.html')


@home_bp.route('/nosotros')
def nosotros():
    return render_template('nosotros.html')