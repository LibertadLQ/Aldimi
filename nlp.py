import os
import importlib

env = os.environ.get('ALDIMI_ENV', 'local').lower()
module_name = 'aldimi_web' if env in ('prod', 'production') else 'aldimi_web_local'
_module = importlib.import_module(module_name)

# Reexportar funciones y objetos NLP / BD
def chatbot_response_nlp(mensaje: str):
    return _module.chatbot_response_nlp(mensaje)

def registrar_paciente(ciu: str, dni_data=None, lab_data=None):
    return _module.registrar_paciente(ciu=ciu, dni_data=dni_data, lab_data=lab_data)

def listar_pacientes():
    return _module.listar_pacientes()

def listar_alertas():
    return _module.listar_alertas()

def _fmt_lab_resultado(lab, ciu=""):
    return _module._fmt_lab_resultado(lab, ciu=ciu)

# Exponer la base de datos in-memory
_BD = getattr(_module, '_BD', {})

__all__ = ['chatbot_response_nlp', 'registrar_paciente', 'listar_pacientes', 'listar_alertas', '_fmt_lab_resultado', '_BD', '_module']
