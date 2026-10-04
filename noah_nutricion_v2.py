"""noah_nutricion_v2.py — Motor Nutricional NOAH (cálculos reales + IA)"""
import os, json, math
from datetime import date, timedelta

def _sf(v, d=0):
    try:
        f = float(v)
        return f if math.isfinite(f) else d
    except: return d

def calcular_gasto_real(peso, altura, edad, sexo, bio, sesiones_hoy):
    if not all([peso, altura, edad, sexo]): return None
    base = 10*peso + 6.25*altura - 5*edad
    tmb = round(base+5 if str(sexo).upper().startswith('M') else base-161)
    fc_dia = _sf(bio.get('fc_media_dia'),0)
    stress = _sf(bio.get('stress_avg'),30)
    bb = _sf(bio.get('body_battery'),60)
    neat = round(tmb*0.20) if fc_dia<=65 else round(max(tmb*0.15,(fc_dia-60)*8))
    gasto_stress = round(tmb*min(0.12,(stress-40)*0.002)) if stress>40 else 0
    gasto_bb = round((40-bb)*3) if bb>0 and bb<40 else 0
    cal_entreno = 0
    for s in sesiones_hoy:
        cal = _sf(s.get('calorias'))
        if cal>0: cal_entreno += cal
        else:
            tss = _sf(s.get('tss'))
            cal_entreno += round(tss*peso*0.01) if tss>0 else round(_sf(s.get('dur_min'),60)*7)
    return {'tmb':tmb,'neat':neat,'gasto_stress':gasto_stress,'gasto_bb':gasto_bb,
            'cal_entreno':round(cal_entreno),'gasto_total':tmb+neat+gasto_stress+gasto_bb+cal_entreno,
            'explicacion':{'tmb':f'Metabolismo basal: {tmb} kcal',
                'neat':f'Actividad diaria: {neat} kcal'+( f' (FC día: {fc_dia}bpm)' if fc_dia>0 else ''),
                'stress':f'Estrés: +{gasto_stress} kcal (nivel {stress}/100)',
                'bb':f'Desgaste: +{gasto_bb} kcal (BB {bb})',
                'entreno':f'Entrenamiento: {round(cal_entreno)} kcal'}}

def calcular_macros(peso, gasto, dur_h, intensidad, bio, objetivo='mantener'):
    if not peso or not gasto: return None
    # OBJETIVO: ajustar calorias objetivo segun meta del atleta
    gasto_original = gasto
    if objetivo == 'bajar':
        gasto = round(gasto * 0.85)   # deficit 15% — perder grasa
    elif objetivo == 'subir':
        gasto = round(gasto * 1.10)   # superavit 10% — ganar musculo
    # 'mantener' deja gasto igual
    # PROTEINA: fija por peso (prioridad fisiologica) — Phillips/ISSN
    prot_gkg = 1.6 if dur_h < 1.0 else (1.8 if dur_h < 2.0 else 2.0)
    if intensidad >= 0.90: prot_gkg += 0.2
    if objetivo == 'bajar': prot_gkg += 0.4   # mas proteina en deficit (preservar musculo)
    prot_g = round(peso * prot_gkg)
    prot_kcal = prot_g * 4

    # CHO: segun carga de entrenamiento del dia (Burke/ISSN)
    # Dia descanso: 3 g/kg. Sube con duracion e intensidad.
    if dur_h < 0.3:
        cho_gkg = 3.0        # descanso
    elif dur_h < 1.0:
        cho_gkg = 4.5        # sesion corta
    elif dur_h < 2.0:
        cho_gkg = 6.0        # moderada
    else:
        cho_gkg = 7.0 + min((dur_h - 2.0) * 1.0, 3.0)  # larga, hasta 10
    if intensidad >= 0.85: cho_gkg += 0.5
    hrv = _sf(bio.get('hrv_rmssd'))
    if 0 < hrv < 35: cho_gkg += 0.3
    if _sf(bio.get('body_battery'), 60) < 30: cho_gkg += 0.3
    cho_gkg = min(cho_gkg, 11.0)
    cho_g = round(peso * cho_gkg)
    cho_kcal = cho_g * 4

    # GRASA: completa el resto del gasto (asegura minimo 0.8 g/kg para hormonas)
    grasa_min = round(peso * 0.8)
    grasa_resto = round((gasto - cho_kcal - prot_kcal) / 9)
    grasa_g = max(grasa_min, grasa_resto)
    grasa_kcal = grasa_g * 9

    total = cho_kcal + prot_kcal + grasa_kcal
    # Si el total se pasa mucho del gasto, recortar CHO (no proteina ni grasa minima)
    if total > gasto * 1.1 and cho_g > peso * 3:
        exceso_kcal = total - round(gasto * 1.05)
        cho_g = max(round(peso * 3), cho_g - round(exceso_kcal / 4))
        cho_kcal = cho_g * 4
        total = cho_kcal + prot_kcal + grasa_kcal

    return {'cho_g':cho_g,'cho_gkg':round(cho_g/peso,1),'prot_g':prot_g,'prot_gkg':round(prot_gkg,1),
            'grasa_g':grasa_g,'grasa_gkg':round(grasa_g/peso,1),
            'total_kcal':total,'gasto_kcal':gasto,'gasto_mantenimiento':gasto_original,
            'objetivo':objetivo}

_RECETAS = {
    'Desayuno': [
        lambda c,p,g: [f'{round(c*0.5/0.6)}g avena','1 banana','1 cda miel',f'{round(p*0.5/0.033)}ml leche',f'{round(p*0.3)}g whey' if p>20 else None],
        lambda c,p,g: [f'{round(p*0.5/0.13)}g huevos',f'{round(c*0.6/0.5)}g pan integral','1/2 palta','1 naranja'],
        lambda c,p,g: [f'{round(p*0.6/0.1)}g yogur griego',f'{round(c*0.4/0.6)}g granola','Frutos rojos','1 cda chía'],
        lambda c,p,g: [f'{round(c*0.5/0.3)}g tostadas',f'{round(p*0.4/0.2)}g queso cottage','1 banana',f'{round(p*0.3)}g whey' if p>20 else None],
    ],
    'Snack AM': [
        lambda c,p,g: [f'{round(p/0.1)}g yogur griego','1 puñado almendras'],
        lambda c,p,g: ['1 banana',f'{round(g/0.5)}g mantequilla maní'],
        lambda c,p,g: [f'{round(p*0.6)}g whey + agua','1 manzana'],
        lambda c,p,g: ['Frutos secos mixtos',f'{round(c*0.4/0.15)}g uvas'],
    ],
    'Almuerzo': [
        lambda c,p,g: [f'{round(p*0.6/0.25)}g pollo',f'{round(c*0.6/0.28)}g arroz integral',f'Ensalada + {round(g*0.4)}ml aceite','1 fruta'],
        lambda c,p,g: [f'{round(p*0.6/0.22)}g carne magra',f'{round(c*0.6/0.20)}g batata','Verduras salteadas',f'{round(g*0.3)}g palta'],
        lambda c,p,g: [f'{round(p*0.6/0.24)}g pescado',f'{round(c*0.6/0.28)}g quinoa','Vegetales vapor',f'{round(g*0.4)}ml aceite oliva'],
        lambda c,p,g: [f'{round(p*0.5/0.25)}g pollo + legumbres',f'{round(c*0.6/0.28)}g pasta integral','Ensalada mixta'],
    ],
    'Snack PM': [
        lambda c,p,g: [f'{round(p/0.06)}g queso',f'{round(c*0.5/0.5)}g pan integral'],
        lambda c,p,g: ['Batido whey + leche','1 puñado nueces'],
        lambda c,p,g: [f'{round(p*0.8/0.1)}g yogur','Granola + miel'],
        lambda c,p,g: ['Tostada + palta',f'{round(p*0.5/0.13)}g huevo duro'],
    ],
    'Cena': [
        lambda c,p,g: [f'{round(p*0.6/0.22)}g pescado',f'{round(c*0.5/0.20)}g batata','Vegetales grillados',f'{round(g*0.3)}g frutos secos'],
        lambda c,p,g: [f'{round(p*0.6/0.25)}g pollo',f'{round(c*0.5/0.28)}g arroz','Ensalada grande',f'{round(g*0.4)}ml aceite oliva'],
        lambda c,p,g: [f'{round(p*0.5/0.13)}g tortilla huevos',f'{round(c*0.5/0.20)}g calabaza','Verduras asadas',f'{round(g*0.3)}g queso'],
        lambda c,p,g: [f'{round(p*0.6/0.24)}g salmón',f'{round(c*0.4/0.20)}g quinoa','Brócoli y zanahoria','1/2 palta'],
    ],
}

def _macros_a_alimentos(momento, cho, prot, grasa, variante=0):
    recetas = _RECETAS.get(momento)
    if not recetas:
        r = ['1 banana' if cho>15 else '1 manzana']
        if prot>5: r.append(f'{round(prot/0.06)}g yogur griego')
        return [x for x in r if x]
    return [x for x in recetas[variante % len(recetas)](cho, prot, grasa) if x]


def _suplementos_dia(peso, dur_h, intensidad, bio):
    sup = [{'nombre':'Creatina monohidrato','dosis':'3-5g/día','momento':'Constante, cualquier hora'}]
    if peso and peso*1.8 > 120:
        sup.append({'nombre':'Proteína whey','dosis':f'{round(peso*0.3)}g','momento':'Post-entreno'})
    if dur_h >= 1.5 or intensidad >= 0.85:
        sup.append({'nombre':'Maltodextrina','dosis':f'{round(dur_h*40)}g','momento':'Durante sesiones largas'})
    if _sf(bio.get('hrv_rmssd'))>0 and _sf(bio.get('hrv_rmssd'))<35:
        sup.append({'nombre':'Omega-3','dosis':'2-3g EPA/DHA','momento':'Con comidas'})
    if _sf(bio.get('sleep_h'))>0 and _sf(bio.get('sleep_h'))<6.5:
        sup.append({'nombre':'Magnesio','dosis':'300-400mg','momento':'Antes de dormir'})
    if intensidad >= 0.9:
        sup.append({'nombre':'Cafeína','dosis':'3-6mg/kg','momento':'30-45min pre-sesión clave'})
    return sup

def calcular_5_comidas(macros, bio, entreno_am, entreno_pm, fecha=None):
    if not macros: return []
    cho,prot,grasa = macros['cho_g'],macros['prot_g'],macros['grasa_g']
    if entreno_am and entreno_pm: dist=[0.25,0.08,0.28,0.12,0.27]
    elif entreno_am: dist=[0.18,0.07,0.32,0.13,0.30]
    elif entreno_pm: dist=[0.25,0.10,0.25,0.08,0.32]
    else: dist=[0.25,0.10,0.30,0.10,0.25]
    nombres=['Desayuno','Snack AM','Almuerzo','Snack PM','Cena']
    import datetime as _dt
    try: variante = _dt.date.fromisoformat(str(fecha)).timetuple().tm_yday if fecha else _dt.date.today().timetuple().tm_yday
    except: variante = 0
    extras_cena=[]
    if bio:
        if _sf(bio.get('sleep_h'))<6: extras_cena.append('Triptófano: banana, leche, nueces')
        if _sf(bio.get('hrv_rmssd'))>0 and _sf(bio.get('hrv_rmssd'))<35: extras_cena.append('Omega-3: salmón, chía')
        if _sf(bio.get('stress_avg'))>50: extras_cena.append('Antioxidantes: frutas colores')
    comidas=[]
    for i,(nm,p) in enumerate(zip(nombres,dist)):
        c_cho,c_prot,c_grasa=round(cho*p),round(prot*p),round(grasa*p)
        c={'nombre':nm,'kcal':c_cho*4+c_prot*4+c_grasa*9,'cho_g':c_cho,'prot_g':c_prot,
           'grasa_g':c_grasa,'alimentos':[a for a in _macros_a_alimentos(nm,c_cho,c_prot,c_grasa,variante+i) if a]}
        if i==4 and extras_cena: c['extras_bio']=extras_cena
        comidas.append(c)
    return comidas

def calcular_durante(sesion, peso):
    dep=sesion.get('deporte','running'); dur=_sf(sesion.get('dur_min'),60)
    tss=_sf(sesion.get('tss')); dur_h=dur/60
    intf=min((tss/(dur_h*100))**0.5,1.2) if tss>0 and dur_h>0 else 0.75
    cho_h=0
    if dur>=75: cho_h=min(round(20+dur_h*15+intf*20),90)
    ml_h=round(peso*5.5) if peso else 400
    if dep=='swimming': ml_h=round(ml_h*0.4)
    elif dep=='running': ml_h=round(ml_h*0.85)
    sodio=round(500+intf*200) if dur>=60 else 0
    prods=[]
    if cho_h>0:
        prods.append(f'{max(1,round(cho_h/25))} gel/hora ({cho_h}g CHO/h)')
        if cho_h>=60: prods.append('Mix glucosa+fructosa 2:1')
        prods.append(f'{ml_h}ml/h líquido + {sodio}mg sodio/h')
    else: prods.append(f'{ml_h}ml/h agua — sesión <75min, no requiere CHO extra')
    return {'deporte':dep,'duracion':dur,'cho_g_hora':cho_h,'cho_g_total':round(cho_h*dur_h),
            'liquido_ml_hora':ml_h,'liquido_ml_total':round(ml_h*dur_h),'sodio_mg_hora':sodio,
            'productos':prods,'necesita_cho':cho_h>0}

def calcular_post(sesion, peso, bio, hay_otra):
    cal=_sf(sesion.get('calorias')); dur=_sf(sesion.get('dur_min'),60)
    tss=_sf(sesion.get('tss')); dur_h=dur/60
    intf=min((tss/(dur_h*100))**0.5,1.2) if tss>0 and dur_h>0 else 0.75
    prot_g=round(min(max(peso*(0.25+intf*0.08),20),40))
    if hay_otra: cho_g=round(peso*1.2*min(dur_h,4)); urgencia='alta'
    else: cho_g=round(cal*0.5/4) if cal>0 else round(peso*1.0); urgencia='normal'
    ml=round(cal*1.5) if cal>0 else round(dur*10)
    return {'deporte':sesion.get('deporte'),'calorias_gastadas':round(cal),'proteina_g':prot_g,
            'cho_g':cho_g,'ml_rehidratacion':ml,'urgencia':urgencia,
            'inmediato':[f'Batido: {prot_g}g whey + banana + 300ml leche',
                         f'200g yogur griego + granola + banana'],
            'comida':[f'{round(prot_g/0.25)}g pollo + {round(cho_g*0.6/0.28)}g arroz + ensalada',
                      f'{round(cho_g*0.5/0.25)}g pasta + {round(prot_g/0.22)}g atún + salsa']}

def alertas_bio(bio):
    if not bio: return []
    a=[]
    bb=_sf(bio.get('body_battery')); sleep=_sf(bio.get('sleep_h'))
    stress=_sf(bio.get('stress_avg')); hrv=_sf(bio.get('hrv_rmssd'))
    if 0<bb<25: a.append({'tipo':'critico','texto':f'Body battery {bb} — reservas agotadas','ajuste':'CHO +20%'})
    elif 0<bb<40: a.append({'tipo':'alerta','texto':f'Body battery bajo ({bb})','ajuste':'Snack extra con CHO'})
    if 0<sleep<5.5: a.append({'tipo':'critico','texto':f'Sueño {sleep:.1f}h','ajuste':'Triptófano en cena + magnesio'})
    elif 0<sleep<6.5: a.append({'tipo':'alerta','texto':f'Sueño {sleep:.1f}h','ajuste':'Triptófano en cena'})
    if stress>55: a.append({'tipo':'alerta','texto':f'Estrés {stress:.0f}/100','ajuste':'Antioxidantes, menos cafeína'})
    if 0<hrv<30: a.append({'tipo':'alerta','texto':f'HRV {hrv:.0f}','ajuste':'Omega-3, magnesio'})
    return a

PROMPT_EAT="""Sos un calculador nutricional. El usuario dice qué comió. Respondé SOLO JSON:
{"alimentos":[{"nombre":"...","cantidad_g":200,"cho_g":0,"prot_g":50,"grasa_g":6,"kcal":254}],
"total":{"cho_g":0,"prot_g":50,"grasa_g":6,"kcal":254}}
Estimá cantidades si no las dice. Tabla USDA/ARGENFOODS."""

def noah_eat_parsear(texto):
    import requests
    key=os.environ.get('GROQ_API_KEY')
    if not key: return {'ok':False,'error':'GROQ_API_KEY no configurada'}
    try:
        r=requests.post('https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},
            json={'model':os.environ.get('GROQ_MODEL','openai/gpt-oss-120b'),
                  'messages':[{'role':'system','content':PROMPT_EAT},{'role':'user','content':texto}],
                  'max_tokens':800,'temperature':0.1},timeout=15)
        if r.status_code!=200: return {'ok':False,'error':f'Error {r.status_code}'}
        t=r.json()['choices'][0]['message']['content'].strip()
        if t.startswith('```'): t=t.split('\n',1)[1]
        if t.endswith('```'): t=t[:-3]
        p=json.loads(t.strip()); p['ok']=True; return p
    except Exception as e: return {'ok':False,'error':str(e)}

def noah_eat_balance(macros_obj, comido):
    if not comido.get('ok') or not macros_obj: return None
    t=comido.get('total',{})
    cho_c,prot_c,grasa_c=_sf(t.get('cho_g')),_sf(t.get('prot_g')),_sf(t.get('grasa_g'))
    cho_o,prot_o,grasa_o=macros_obj['cho_g'],macros_obj['prot_g'],macros_obj['grasa_g']
    fc,fp,fg=max(0,cho_o-cho_c),max(0,prot_o-prot_c),max(0,grasa_o-grasa_c)
    sug=[]
    if fp>15: sug.append(f'Falta {fp}g proteína → {round(fp/0.25)}g pollo o {round(fp/0.8)}g whey')
    if fc>30: sug.append(f'Falta {fc}g CHO → {round(fc/0.28)}g arroz o {round(fc/0.23)}g banana')
    if fg>10: sug.append(f'Falta {fg}g grasa → {round(fg/0.50)}g frutos secos')
    return {'comido':{'cho_g':cho_c,'prot_g':prot_c,'grasa_g':grasa_c,'kcal':_sf(t.get('kcal'))},
            'objetivo':{'cho_g':cho_o,'prot_g':prot_o,'grasa_g':grasa_o},
            'falta':{'cho_g':fc,'prot_g':fp,'grasa_g':fg},
            'pct':{'cho':round(min(cho_c/max(cho_o,1)*100,100)),
                   'prot':round(min(prot_c/max(prot_o,1)*100,100)),
                   'grasa':round(min(grasa_c/max(grasa_o,1)*100,100))},
            'sugerencias':sug}

def nutricion_dia(conn, atleta_id, fecha=None):
    fecha=fecha or str(date.today()); cur=conn.cursor()
    cur.execute('SELECT nombre,peso_kg,altura_cm,edad,sexo FROM atletas WHERE id=%s',[atleta_id])
    row=cur.fetchone()
    if not row: return {'disponible':False,'error':'Atleta no encontrado'}
    nombre,peso,altura,edad,sexo=row
    # Objetivo nutricional del atleta (columna opcional)
    objetivo_nut = 'mantener'
    try:
        cur.execute('SELECT objetivo_nutricional FROM atletas WHERE id=%s',[atleta_id])
        _o = cur.fetchone()
        if _o and _o[0]: objetivo_nut = _o[0]
    except Exception: pass
    if not peso: return {'disponible':False,'error':'Falta peso'}
    cur.execute('''SELECT hrv_rmssd,sleep_h,stress_avg,body_battery,recovery_score,stress_intra,fc_media_dia
        FROM sleep_hrv WHERE atleta_id=%s AND fecha<=%s ORDER BY fecha DESC LIMIT 1''',[atleta_id,fecha])
    br=cur.fetchone(); bio={}
    if br: bio={'hrv_rmssd':br[0],'sleep_h':br[1],'stress_avg':br[2],'body_battery':br[3],
                'recovery_score':br[4],'stress_intra':br[5],'fc_media_dia':br[6]}
    cur.execute('SELECT sport,duration_min,tss_total,calorias,intensity_factor FROM sesiones WHERE atleta_id=%s AND fecha=%s AND tss_total>0 ORDER BY id',
                [atleta_id,fecha])
    sesiones=[{'deporte':s[0],'dur_min':_sf(s[1],60),'tss':_sf(s[2]),'calorias':_sf(s[3]),'if_real':_sf(s[4])} for s in cur.fetchall()]
    gasto=calcular_gasto_real(peso,altura,edad,sexo,bio,sesiones)
    if not gasto: return {'disponible':False,'error':'No se pudo calcular'}
    dur_h=sum(s['dur_min'] for s in sesiones)/60; if_max=0.70
    for s in sesiones:
        if s.get('if_real') and s['if_real']>0:
            si = s['if_real']   # IF real de la sesion (desde potencia/pace)
        else:
            # Proxy conservador: TSS/(dur*100) sin raiz (la raiz inflaba sesiones cortas)
            dh=max(s['dur_min'],1)/60
            si = min(s['tss']/(dh*100), 1.1) if s['tss']>0 else 0.70
        if_max=max(if_max,si)
    macros=calcular_macros(peso,gasto['gasto_total'],dur_h,if_max,bio,objetivo_nut)
    comidas=calcular_5_comidas(macros,bio,len(sesiones)>=1,len(sesiones)>=2,fecha)
    durante=[calcular_durante(s,peso) for s in sesiones]
    post=[calcular_post(s,peso,bio,i<len(sesiones)-1) for i,s in enumerate(sesiones)]
    suplementos = _suplementos_dia(peso, dur_h, if_max, bio)
    return {'disponible':True,'atleta':nombre,'fecha':fecha,'gasto':gasto,'macros':macros,
            'comidas':comidas,'durante':durante,'post':post,'alertas':alertas_bio(bio),
            'suplementos':suplementos,
            'hidratacion':{'ml_dia':round(peso*35)+sum(d['liquido_ml_total'] for d in durante),
                           'ml_base':round(peso*35),'ml_entreno':sum(d['liquido_ml_total'] for d in durante)}}

def construir_recomendacion_durante(deporte,dur_min,intensidad_if,peso_kg=None,temperatura_c=20):
    r=calcular_durante({'deporte':deporte,'dur_min':dur_min,'tss':dur_min*intensidad_if**2*100/60},peso_kg or 70)
    return {'cho':{'cho_g_hora':r['cho_g_hora'],'cho_g_total':r['cho_g_total'],'necesita':r['necesita_cho'],
            'mensaje':r['productos'][0] if r['productos'] else ''},
            'hidratacion':{'liquido_ml_hora':r['liquido_ml_hora']},
            'texto_corto':r['productos'][0] if r['productos'] else 'Hidratarse'}

def construir_recomendacion_post(peso_kg,dur_real_min,intensidad_if_real,proxima_sesion_exigente_24h=None):
    r=calcular_post({'dur_min':dur_real_min,'tss':dur_real_min*intensidad_if_real**2*100/60,'calorias':dur_real_min*8},
                    peso_kg,{},proxima_sesion_exigente_24h or False)
    return {'recuperacion':{'proteina_g_por_toma':r['proteina_g'],'cho_mensaje':f'{r["cho_g"]}g CHO'},
            'rehidratacion':{'liquido_reposicion_ml':r['ml_rehidratacion']},
            'texto_corto':f'Prot {r["proteina_g"]}g · CHO {r["cho_g"]}g · {r["ml_rehidratacion"]}ml'}
