from backend.alertas import evaluar_pruebas

tests = [
    {"nombre": "Hemoglobina (Hb)", "valor": "6.5", "flag": ""},
    {"nombre": "Plaquetas", "valor": "25000", "flag": ""},
    {"nombre": "Potasio (K)", "valor": "6.2", "flag": ""},
    {"nombre": "Creatinina", "valor": "2.0", "flag": ""},
    {"nombre": "Proteína C Reactiva (CRP)", "valor": "60", "flag": ""},
]

alerts = evaluar_pruebas(tests)
print(f"Generó {len(alerts)} alertas")
for a in alerts:
    print(a)
