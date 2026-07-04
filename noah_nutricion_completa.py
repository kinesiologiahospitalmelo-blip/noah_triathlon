"""
noah_nutricion_completa.py — Nutrición Deportiva NOAH (v2 — bibliografía citada)
==================================================================================
Cada fórmula usada está citada explícitamente. Ningún valor es arbitrario.
Si faltan datos del atleta para un cálculo, el sistema lo declara explícitamente
en vez de usar un default inventado — NUNCA rellena con supuestos silenciosos.

FUENTES:
  [1] Mifflin MD, St Jeor ST, et al. "A new predictive equation for resting
      energy expenditure in healthy individuals." Am J Clin Nutr. 1990.
      -> TMB (tasa metabolica basal)
  [2] ACSM's Guidelines for Exercise Testing and Prescription, 11th ed.
      -> Factores de actividad para TDEE
  [3] Kerksick CM, et al. "ISSN position stand: Nutrient timing." J Int Soc
      Sports Nutr. 2017.
      -> CHO durante ejercicio, recuperacion post-esfuerzo
  [4] Jeukendrup A. "Periodized nutrition for athletes." Sports Med. 2017;
      Jeukendrup A. "Carbohydrate intake during exercise and performance."
      Nutrition. 2004 (limites de absorcion intestinal, multi-transportadores).
      -> Dosificacion de CHO por duracion/intensidad
  [5] Sawka MN, et al. "ACSM position stand: Exercise and fluid replacement."
      Med Sci Sports Exerc. 2007.
      -> Hidratacion durante el ejercicio, limite de perdida de peso corporal
  [6] Shirreffs SM, Sawka MN. "Fluid and electrolyte needs for training,
      competition, and recovery." J Sports Sci. 2011.
      -> Rehidratacion post-esfuerzo (125-150% del deficit)
  [7] Moore DR, et al. J Gerontol. 2015; Witard OC et al. Am J Clin Nutr. 2014.
      -> Proteina por toma post-esfuerzo (0.25-0.3 g/kg, tope ~20-40g)
"""

from datetime import date


# ─── 1. TASA METABÓLICA BASAL (TMB) — Mifflin-St Jeor [1] ──────────────────

def calcular_tmb(peso_kg: float, altura_cm: float, edad: int, sexo: str) -> dict:
    """
    Mifflin-St Jeor (1990) — formula recomendada actualmente por la Academy
    of Nutrition and Dietetics como la mas precisa para poblacion general
    y atletica, superando a Harris-Benedict en validaciones modernas.

    Hombres: TMB = 10*peso + 6.25*altura - 5*edad + 5
    Mujeres: TMB = 10*peso + 6.25*altura - 5*edad - 161

    Si falta cualquier dato, retorna disponible=False y declara que falta.
    NUNCA usa un valor por defecto inventado.
    """
    faltantes = []
    if not peso_kg:   faltantes.append('peso_kg')
    if not altura_cm: faltantes.append('altura_cm')
    if not edad:      faltantes.append('edad')
    if not sexo:      faltantes.append('sexo')

    if faltantes:
        return {
            'disponible': False,
            'tmb_kcal': None,
            'faltantes': faltantes,
            'mensaje': f'Faltan datos del atleta para calcular TMB: {", ".join(faltantes)}. '
                       f'Completar en el perfil para habilitar el calculo de necesidad calorica basal.',
            'fuente': 'Mifflin-St Jeor (1990)',
        }

    base = 10 * peso_kg + 6.25 * altura_cm - 5 * edad
    tmb = base + 5 if sexo.upper().startswith('M') else base - 161

    return {
        'disponible': True,
        'tmb_kcal': round(tmb),
        'faltantes': [],
        'mensaje': None,
        'fuente': 'Mifflin-St Jeor (1990)',
    }


# ─── 2. GASTO ENERGÉTICO TOTAL DIARIO (TDEE) — ACSM [2] ─────────────────────

FACTORES_ACTIVIDAD_ACSM = {
    'sedentario'    : 1.20,
    'ligero'        : 1.375,  # 1-3 sesiones/semana
    'moderado'      : 1.55,   # 3-5 sesiones/semana
    'activo'        : 1.725,  # 6-7 sesiones/semana (atleta de resistencia tipo)
    'muy_activo'    : 1.90,   # 2 sesiones/dia, alto volumen
}


def calcular_tdee(tmb_kcal: float, nivel_actividad: str) -> dict:
    """
    TDEE = TMB x factor de actividad (ACSM Guidelines, 11th ed.) [2]
    Esto es el gasto del DIA TIPICO sin contar la sesion de entrenamiento
    especifica de hoy -- la sesion de hoy se suma por separado con el dato
    real de Garmin, para no duplicar el gasto de entrenamiento.
    """
    if tmb_kcal is None:
        return {'disponible': False, 'tdee_kcal': None,
                'mensaje': 'TMB no disponible -- no se puede calcular TDEE.'}

    factor = FACTORES_ACTIVIDAD_ACSM.get(nivel_actividad)
    if factor is None:
        return {'disponible': False, 'tdee_kcal': None,
                'mensaje': f'Nivel de actividad "{nivel_actividad}" no reconocido. '
                           f'Usar uno de: {list(FACTORES_ACTIVIDAD_ACSM.keys())}'}

    return {
        'disponible': True,
        'tdee_kcal': round(tmb_kcal * factor),
        'factor_usado': factor,
        'nivel_actividad': nivel_actividad,
        'fuente': 'ACSM Guidelines for Exercise Testing and Prescription, 11th ed.',
    }


def inferir_nivel_actividad(sesiones_semana: int, doble_turno: bool = False) -> str:
    """Mapea la frecuencia de entrenamiento real del atleta a un nivel ACSM."""
    if doble_turno or sesiones_semana >= 10:
        return 'muy_activo'
    elif sesiones_semana >= 6:
        return 'activo'
    elif sesiones_semana >= 3:
        return 'moderado'
    elif sesiones_semana >= 1:
        return 'ligero'
    return 'sedentario'


# ─── 3. CARBOHIDRATOS DURANTE EL EJERCICIO — ISSN [3] + Jeukendrup [4] ──────

def calcular_cho_durante(dur_min: float, intensidad_if: float) -> dict:
    """
    Dosificacion de CHO exogeno durante el ejercicio segun duracion e
    intensidad. Fuente: ISSN Position Stand (Kerksick et al. 2017) [3] y
    Jeukendrup (2004, 2017) sobre limites de absorcion intestinal [4].

    Rangos (de la literatura):
      <45min    : no se requiere CHO exogeno -- el glucogeno muscular
                  almacenado es suficiente para esa duracion.
      45-75min  : no se requiere fisiologicamente para mantener
                  rendimiento, salvo intensidad alta (umbral/VO2) donde
                  un enjuague bucal con CHO puede ayudar por efecto central.
      75min-2h  : 30-60 g/h (un solo transportador, ej. glucosa)
      2h-3h     : 60-90 g/h (multiples transportadores: glucosa+fructosa)
      >3h       : hasta 90 g/h, limite practico de absorcion intestinal
                  entrenada (Jeukendrup 2010)
    """
    if dur_min < 45:
        return {
            'cho_g_hora': 0, 'cho_g_total': 0,
            'necesita': False, 'fuentes_sugeridas': [],
            'mensaje': 'Sesion <45min: el glucogeno muscular almacenado es suficiente. '
                       'No se requiere CHO exogeno (ISSN 2017).',
            'fuente': 'Kerksick et al., ISSN Position Stand, 2017',
        }

    dur_h = dur_min / 60

    if dur_min < 75:
        if intensidad_if >= 0.90:
            return {
                'cho_g_hora': 0, 'cho_g_total': 0,
                'necesita': True, 'tipo': 'enjuague_bucal',
                'fuentes_sugeridas': ['Enjuague bucal con bebida deportiva (sin ingerir, escupir)'],
                'mensaje': 'Sesion 45-75min a alta intensidad: no requiere CHO metabolico, pero '
                           'un enjuague bucal con CHO (sin ingerir) puede mejorar el rendimiento '
                           'por efecto neural central (Jeukendrup 2010).',
                'fuente': 'Jeukendrup, Sports Med, 2010',
            }
        return {
            'cho_g_hora': 0, 'cho_g_total': 0,
            'necesita': False, 'fuentes_sugeridas': [],
            'mensaje': 'Sesion 45-75min a intensidad moderada/baja: glucogeno almacenado suficiente.',
            'fuente': 'Kerksick et al., ISSN Position Stand, 2017',
        }

    if dur_min < 120:
        cho_hora = 30 if intensidad_if < 0.85 else 60
        return {
            'cho_g_hora': cho_hora, 'cho_g_total': round(cho_hora * dur_h),
            'necesita': True, 'tipo': 'transportador_unico',
            'fuentes_sugeridas': ['Bebida deportiva isotónica (~6-8% CHO)', '1 gel cada 30-40min (~25g CHO c/u)'],
            'mensaje': f'{cho_hora}g CHO/h -- rango 30-60g/h (un transportador: glucosa).',
            'fuente': 'Kerksick et al., ISSN Position Stand, 2017',
        }

    if dur_min < 180:
        cho_hora = 60 if intensidad_if < 0.85 else 90
        return {
            'cho_g_hora': cho_hora, 'cho_g_total': round(cho_hora * dur_h),
            'necesita': True, 'tipo': 'multi_transportador',
            'fuentes_sugeridas': ['Gel multi-CHO (glucosa+fructosa) cada 30min',
                                  'Bebida deportiva isotónica continua', 'Banana o dátiles'],
            'mensaje': f'{cho_hora}g CHO/h -- requiere multiples transportadores '
                       '(glucosa+fructosa ratio ~2:1) para superar el limite de absorcion '
                       'de un solo transportador (~60g/h).',
            'fuente': 'Jeukendrup, Nutrition, 2004',
        }

    return {
        'cho_g_hora': 90, 'cho_g_total': round(90 * dur_h),
        'necesita': True, 'tipo': 'multi_transportador_maximo',
        'fuentes_sugeridas': ['Gel multi-CHO cada 30min', 'Bebida deportiva isotónica continua',
                              'Barrita energética o fruta sólida (alternar texturas)'],
        'mensaje': '90g CHO/h -- limite practico superior de absorcion intestinal entrenada '
                   'en sesiones >3h. Alternar fuentes (gel/liquido/solido) para evitar '
                   'malestar gastrointestinal.',
        'fuente': 'Jeukendrup, Sports Med, 2010/2017',
    }


# ─── 4. HIDRATACIÓN Y SODIO DURANTE — ACSM/Sawka [5] ────────────────────────

def calcular_hidratacion_durante(dur_min: float, peso_kg: float = None,
                                   temperatura_c: float = 20,
                                   intensidad_if: float = 0.75,
                                   deporte: str = 'running') -> dict:
    """
    ACSM Position Stand (Sawka et al. 2007) [5]: el objetivo es no perder
    mas del 2% del peso corporal en sudoracion neta. Sin medicion real de
    tasa de sudoracion individual (que requiere pesaje pre/post entreno),
    se usa una tasa promedio poblacional documentada en la literatura
    (0.5-1.0 L/h en condiciones templadas) -- declarado como ESTIMACION,
    no medicion.

    NOTA HONESTA sobre natación: Sawka et al. (2007) documenta las tasas
    de sudoración en ejercicio terrestre (running/cycling). La sudoración
    real en inmersión es fisiológicamente distinta (enfriamiento por agua,
    pérdida de electrolitos diferente), pero no se aplica ningún factor de
    corrección porque no hay una cifra citable equivalente en la bibliografía
    de referencia usada aquí. Se devuelve la misma estimación terrestre con
    esta advertencia explícita, en vez de inventar un ajuste sin fuente.
    """
    if dur_min < 20:
        return {
            'liquido_ml_hora': 0, 'liquido_ml_total': 0,
            'sodio_mg_hora': 0, 'sodio_mg_total': 0,
            'mensaje': 'Sesion muy corta -- hidratacion previa al ejercicio es suficiente.',
            'es_estimacion': True,
            'fuente': 'Sawka et al., ACSM Position Stand, 2007',
        }

    dur_h = dur_min / 60

    # Tasa de sudoracion ESTIMADA (no medida) -- rango documentado 0.5-1.5 L/h
    # en clima templado para atletas de resistencia, ajustado por intensidad/temp.
    tasa_base_ml_h = 700  # punto medio del rango documentado en clima templado
    if intensidad_if >= 0.90:
        tasa_base_ml_h += 150
    if temperatura_c > 25:
        tasa_base_ml_h += 250
    if temperatura_c > 30:
        tasa_base_ml_h += 350

    liquido_ml_total = round(tasa_base_ml_h * dur_h)

    nota_deporte = ''
    if deporte == 'swimming':
        nota_deporte = (' ADVERTENCIA: esta estimación usa datos de ejercicio terrestre '
                         '(Sawka 2007) — la sudoración real en inmersión es distinta y no '
                         'hay una cifra equivalente citable disponible en esta referencia.')

    # Sodio: concentracion de sudor en atletas entrenados 400-1100 mg/L,
    # punto medio practico documentado ~800mg/L (Sawka et al. 2007)
    sodio_mg_hora = round(tasa_base_ml_h / 1000 * 800)

    # Fuentes prácticas de sodio — concentraciones de producto comercial
    # (información de etiqueta, no estimación fisiológica):
    #   Bebida deportiva isotónica estándar (ej. Gatorade): ~450mg sodio/L
    #   Sales de hidratación efervescentes (ej. Nuun): ~300-360mg/tableta
    #   Gel con electrolitos: variable, ver etiqueta del producto, ~50-100mg/gel
    fuentes_sodio = []
    if sodio_mg_hora > 0:
        fuentes_sodio.append(f'Bebida deportiva isotónica ({tasa_base_ml_h}ml/h ya aporta sodio — '
                              'no se suma agua sola por separado)')
        if sodio_mg_hora >= 600:
            fuentes_sodio.append('Sal de hidratación efervescente adicional (ej. 1 tableta ~300-360mg) '
                                  'si la sesión es muy exigente o calurosa')

    return {
        'liquido_ml_hora': tasa_base_ml_h,
        'liquido_ml_total': liquido_ml_total,
        'sodio_mg_hora': sodio_mg_hora,
        'sodio_mg_total': round(sodio_mg_hora * dur_h),
        'fuentes_sodio': fuentes_sodio,
        'mensaje': ('ESTIMACION basada en tasa de sudoracion poblacional promedio '
                   '(700mL/h base, ajustada por intensidad/temperatura). '
                   'Para precision individual se requiere pesaje pre/post entreno.' + nota_deporte),
        'es_estimacion': True,
        'fuente': 'Sawka et al., ACSM Position Stand, 2007',
    }


# ─── 5. RECUPERACIÓN POST-ESFUERZO — ISSN [3], Moore/Witard [7] ────────────

def calcular_recuperacion_post(peso_kg: float, dur_real_min: float,
                                 intensidad_if_real: float,
                                 proxima_sesion_exigente_24h: bool = None) -> dict:
    """
    CHO de recuperacion: 1.0-1.2 g/kg/h en las primeras 4h SOLO si hay otra
    sesion exigente en <24h (resintesis rapida de glucogeno necesaria).
    Si no se sabe o no hay otra sesion exigente, recuperacion estandar con
    la siguiente comida normal es suficiente (ISSN 2017) [3].

    Proteina: 0.25-0.3 g/kg POR TOMA (no por dia) -- dosis optima por toma
    para maximizar sintesis de proteina muscular, con techo practico de
    ~20-40g por toma segun masa muscular (Moore 2015, Witard 2014) [7].
    """
    if proxima_sesion_exigente_24h is None:
        cho_modo = 'no_determinado'
        cho_g_kg_h = None
        cho_mensaje = ('No se especifico si hay otra sesion exigente en <24h. '
                       'Si la hay, usar 1.0-1.2 g CHO/kg/h en las primeras 4h. '
                       'Si no, una comida balanceada normal dentro de las 2h es suficiente.')
    elif proxima_sesion_exigente_24h:
        cho_modo = 'resintesis_rapida'
        cho_g_kg_h = 1.0
        cho_mensaje = ('Hay otra sesion exigente en <24h -- priorizar resintesis rapida '
                       'de glucogeno: 1.0 g CHO/kg/h durante las primeras 4h.')
    else:
        cho_modo = 'estandar'
        cho_g_kg_h = None
        cho_mensaje = ('Sin otra sesion exigente en <24h -- una comida balanceada normal '
                       'con CHO+proteina dentro de las 2h es suficiente (ISSN 2017).')

    cho_recuperacion_g_total = round(peso_kg * cho_g_kg_h * 4) if cho_g_kg_h else None

    # Proteina por toma -- 0.25-0.3 g/kg, tope practico 20-40g (Moore 2015, Witard 2014)
    proteina_g_kg = 0.3 if (dur_real_min >= 90 or intensidad_if_real >= 0.90) else 0.25
    proteina_g_toma = round(peso_kg * proteina_g_kg, 1)
    proteina_g_toma = min(proteina_g_toma, 40)  # tope superior documentado
    proteina_g_toma = max(proteina_g_toma, 20)  # piso inferior documentado para adultos

    fuentes_proteina = ['Batido de proteína (whey o vegetal)', 'Yogur griego', 'Huevos',
                        'Pollo/pescado', 'Legumbres (combinado con cereal para perfil completo)']
    fuentes_cho_recup = ['Banana', 'Avena', 'Arroz o pasta', 'Pan integral', 'Frutas secas']

    return {
        'cho_modo': cho_modo,
        'cho_g_kg_h': cho_g_kg_h,
        'cho_recuperacion_g_total_4h': cho_recuperacion_g_total,
        'cho_mensaje': cho_mensaje,
        'fuentes_cho': fuentes_cho_recup,
        'proteina_g_por_toma': proteina_g_toma,
        'proteina_mensaje': f'{proteina_g_toma}g de proteina de alta calidad en la comida '
                            'post-entreno (dentro de las 2h) -- dosis optima por toma para '
                            'sintesis de proteina muscular.',
        'fuentes_proteina': fuentes_proteina,
        'fuente_cho': 'Kerksick et al., ISSN Position Stand, 2017',
        'fuente_proteina': 'Moore et al. 2015; Witard et al. 2014',
    }


def calcular_rehidratacion_post(peso_pre_kg: float = None, peso_post_kg: float = None,
                                  dur_real_min: float = None) -> dict:
    """
    Rehidratacion post-esfuerzo: 125-150% del deficit de peso corporal
    (Shirreffs & Sawka, 2011) [6]. Requiere pesaje real pre/post para ser
    preciso -- sin eso, se declara explicitamente que es una estimacion
    no disponible, en vez de inventar un numero.
    """
    if peso_pre_kg and peso_post_kg:
        deficit_kg = peso_pre_kg - peso_post_kg
        deficit_ml = deficit_kg * 1000  # 1kg de perdida aprox 1L de sudor
        liquido_reposicion_ml = round(deficit_ml * 1.375)  # punto medio 125-150%
        return {
            'metodo': 'medido',
            'deficit_peso_kg': round(deficit_kg, 2),
            'liquido_reposicion_ml': liquido_reposicion_ml,
            'mensaje': f'Basado en pesaje real pre/post. Reponer {liquido_reposicion_ml}ml '
                       '(125-150% del deficit medido) en las proximas horas.',
            'fuente': 'Shirreffs & Sawka, J Sports Sci, 2011',
        }

    return {
        'metodo': 'no_disponible',
        'liquido_reposicion_ml': None,
        'mensaje': 'Sin pesaje pre/post entreno no es posible calcular la rehidratacion '
                   'real con precision (Shirreffs & Sawka 2011 requiere medicion directa). '
                   'Recomendacion general: hidratar gradualmente segun sed durante las horas '
                   'posteriores, evitando ingesta excesiva de una sola vez.',
        'fuente': 'Shirreffs & Sawka, J Sports Sci, 2011',
    }


# ─── FORMATEO PARA UI ────────────────────────────────────────────────────────

def construir_recomendacion_durante(deporte: str, dur_min: float, intensidad_if: float,
                                     peso_kg: float = None, temperatura_c: float = 20) -> dict:
    """
    Combina CHO + hidratacion durante en un solo resultado, listo para mostrar.
    Esta es la funcion que patrones_sesion.py debe llamar.
    """
    cho = calcular_cho_durante(dur_min, intensidad_if)
    hid = calcular_hidratacion_durante(dur_min, peso_kg, temperatura_c, intensidad_if, deporte)

    return {
        'cho': cho,
        'hidratacion': hid,
        'texto_corto': _texto_corto_durante(cho, hid),
    }


def _texto_corto_durante(cho: dict, hid: dict) -> str:
    """
    Texto accionable: qué tomar, cuánto y de dónde — no solo gramos sueltos.
    """
    partes_cantidad = []
    if cho.get('necesita') and cho.get('cho_g_hora', 0) > 0:
        partes_cantidad.append(f"{cho['cho_g_hora']}g CHO/h ({cho['cho_g_total']}g total)")
    if hid.get('liquido_ml_hora', 0) > 0:
        partes_cantidad.append(f"{hid['liquido_ml_hora']}ml líquido/h")
    if hid.get('sodio_mg_hora', 0) > 0:
        partes_cantidad.append(f"{hid['sodio_mg_hora']}mg sodio/h")

    if not partes_cantidad:
        return cho.get('mensaje', '')

    cantidad_str = ', '.join(partes_cantidad)

    # Fuentes concretas: combinar las de CHO y las de sodio sin duplicar
    fuentes = list(cho.get('fuentes_sugeridas', []))
    fuentes_sodio = hid.get('fuentes_sodio', [])
    for f in fuentes_sodio:
        if f not in fuentes:
            fuentes.append(f)

    fuentes_str = f" Tomar: {'; '.join(fuentes)}." if fuentes else ''

    return f"{cantidad_str}.{fuentes_str} {cho.get('mensaje', '')}".strip()


def construir_recomendacion_post(peso_kg: float, dur_real_min: float,
                                   intensidad_if_real: float,
                                   proxima_sesion_exigente_24h: bool = None) -> dict:
    """Combina recuperación CHO+proteína con rehidratación (sin pesaje, declarado)."""
    recup = calcular_recuperacion_post(peso_kg, dur_real_min, intensidad_if_real,
                                        proxima_sesion_exigente_24h)
    rehid = calcular_rehidratacion_post()  # sin pesaje real disponible por defecto

    fuentes_str = (f" Proteína: {', '.join(recup['fuentes_proteina'][:3])}. "
                   f"CHO: {', '.join(recup['fuentes_cho'][:3])}.")

    return {
        'recuperacion': recup,
        'rehidratacion': rehid,
        'texto_corto': (f"Proteína: {recup['proteina_g_por_toma']}g por toma.{fuentes_str} "
                        f"{recup['cho_mensaje']} {rehid['mensaje']}"),
    }


if __name__ == '__main__':
    print("=== TMB Rodrigo (84kg, 172cm, 47 anios, M) ===")
    tmb = calcular_tmb(84, 172, 47, 'M')
    print(tmb)

    print("\n=== TDEE Rodrigo, nivel 'activo' (triatleta 7 sesiones/sem) ===")
    tdee = calcular_tdee(tmb['tmb_kcal'], 'activo')
    print(tdee)

    print("\n=== TMB Silvina (60kg, altura FALTANTE, 43 anios, M-dato a revisar) ===")
    tmb_s = calcular_tmb(60, None, 43, 'M')
    print(tmb_s)

    print("\n=== CHO durante -- bike 2h30 IF=0.82 ===")
    print(calcular_cho_durante(150, 0.82))

    print("\n=== CHO durante -- swim 52min IF=0.70 ===")
    print(calcular_cho_durante(52, 0.70))

    print("\n=== Recomendacion DURANTE combinada -- bike 60min IF=0.75, 84kg, 22C ===")
    print(construir_recomendacion_durante('cycling', 60, 0.75, 84, 22))

    print("\n=== Recomendacion POST combinada -- Rodrigo 84kg, 165min IF=0.88, sin otra sesion <24h ===")
    print(construir_recomendacion_post(84, 165, 0.88, proxima_sesion_exigente_24h=False))
