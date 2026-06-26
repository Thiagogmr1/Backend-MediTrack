from fastapi import APIRouter, Query, Depends
from app.database import get_connection
from app.auth import require_role

router = APIRouter()

# Base pré-cadastrada de medicamentos comuns
BASE_MEDICATIONS = [
    "Metformina", "Insulina NPH", "Insulina Regular", "Insulina Glargina",
    "Pioglitazona", "Dapaglifozina", "Semaglutida", "Liraglutida",
    "Tirzepatida", "Orlistate", "Losartana", "Valsartana", "Entresto",
    "Enalapril", "Captopril", "Anlodipino", "Propranolol", "Atenolol",
    "Levotiroxina", "Sinvastatina", "Rosuvastatina", "Atorvastatina",
    "Ezetimiba", "Alenia (formoterol + budesonida)", "Spiolto",
    "Spiriva Respimat", "Salbutamol spray 100mcg/jato", "Fluticasona",
    "Budesonida", "Sertralina", "Fluoxetina", "Venlafaxina",
    "Desvenlafaxina", "Duloxetina", "Pregabalina", "Gabapentina",
    "Donepezila", "Ansitec", "Bupropiona", "Isotretinoína",
    "Metotrexato", "Dienogeste",
]


@router.get("/autocomplete")
def autocomplete_medications(
    q: str = Query(..., min_length=2, description="Termo de busca (mínimo 2 caracteres)"),
    doctor_id: int = Query(..., description="ID do médico para incluir medicamentos personalizados"),
    current_user: dict = Depends(require_role("doctor")),
):
    q_lower = q.strip().lower()

    # 1. Filtra base pré-cadastrada
    base_matches = [m for m in BASE_MEDICATIONS if q_lower in m.lower()]

    # 2. Busca medicamentos já usados pelo médico (nomes únicos, excluindo os da base)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT DISTINCT m.name
            FROM medications m
            JOIN prescriptions p ON p.id = m.prescription_id
            WHERE p.doctor_id = %s
              AND LOWER(m.name) LIKE %s
            ORDER BY m.name
            LIMIT 20
            """,
            (doctor_id, f"%{q_lower}%"),
        )
        doctor_meds = [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

    # 3. Junta os resultados: base primeiro, depois personalizados (sem duplicatas)
    base_set = {m.lower() for m in base_matches}
    custom = [m for m in doctor_meds if m.lower() not in base_set]

    suggestions = base_matches + custom

    return {"suggestions": suggestions[:15]}  # Limita a 15 sugestões no total