from flask import Blueprint, render_template
from app.models.data_model import DataModel

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def dashboard():
    """Módulo Atmosfera: Dashboard com telemetria viva e isolinhas temporais"""
    locais = DataModel.list_locais()
    return render_template('dashboard.html', locais=locais)

@main_bp.route('/analise')
def analytics():
    """Módulo de Análise Técnica & Machine Learning Supervisionado e AR"""
    locais = DataModel.list_locais()
    return render_template('analytics.html', locais=locais)

@main_bp.route('/dados')
def data_management():
    """Módulo de Gestão de Dados: Tabelas, edição, paginação e exclusões"""
    locais = DataModel.list_locais()
    return render_template('data_management.html', locais=locais)

@main_bp.route('/mapa')
def map_view():
    """Módulo Geoespacial: Visualização em Mapa Interativo dos Locais de Coleta"""
    locais = DataModel.list_locais_geo()
    return render_template('mapa.html', locais=locais)