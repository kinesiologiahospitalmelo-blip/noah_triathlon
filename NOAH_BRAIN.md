# NOAH BRAIN — Documento de Visión y Arquitectura
## Versión 1.0 — Julio 2026

---

## QUÉ ES NOAH

NOAH no es un planificador de carga. NOAH es un entrenador que piensa.

La pregunta que responde no es "cuánto TSS esta semana" sino:
**"¿Qué es lo que frena a este atleta y qué entrenamiento específico lo hace más rápido para el día de la carrera?"**

---

## PRINCIPIO FUNDAMENTAL

NOAH prescribe SOLUCIONES, no CARGA.

No dice "500 TSS esta semana en Z3-Z4". Dice:
"Tu limitante es el umbral en bike — FTP estancado 4 semanas. Tu aeróbico está bien.
Tu recuperación está bien. Entonces: 70' con 4×8' a 165W. Eso es lo que te hace
más rápido el día de la carrera."

Y sabe decir "no entrenes" cuando esa es la mejor prescripción.

---

## ARQUITECTURA: 3 PILARES

### PILAR 1 — Diagnóstico de Limitantes

NOAH identifica qué sistema fisiológico está frenando al atleta.

Sistemas independientes (cada uno se adapta con estímulos distintos):

| Sistema | Estímulo | Adaptación | Pérdida | Referencia |
|---------|----------|------------|---------|------------|
| Aeróbico central (corazón, SV) | Volumen Z2 | 8-12 sem | 4-8 sem | Coyle 1988, Seiler 2010 |
| Aeróbico periférico (mito, capilares) | Vol Z2 + Z3-Z4 | 3-6 sem | 2-4 sem | Holloszy 1967 |
| Umbral (clearance lactato) | Z3-Z4 sostenido | 2-4 sem | 2-3 sem | Billat 2001 |
| Neuromuscular (reclutamiento, economía) | Z5+ y fuerza | 2-3 sem | 1-2 sem | Paavolainen 1999 |
| Anaeróbico (glucólisis, W') | Z5-Z6 | 1-2 sem | 1 sem | Tabata 1996 |

NOAH mira los datos del atleta y determina cuáles están fuertes y cuáles débiles:
- Si pace en Z2 mejoró pero umbral no → limitante = umbral
- Si FTP subió pero W'bal se vacía rápido → limitante = anaeróbico
- Si todo está bien pero se funde en la 2da mitad de la carrera → limitante = glucógeno / nutrición
- Si HRV baja sostenido → limitante = recuperación, no entrenar más

### PILAR 2 — Prescripción por Solución

Según la limitante + la fase (A/T/R/Taper) + la distancia de carrera, NOAH prescribe
la sesión ESPECÍFICA que ataca esa limitante.

No son templates. Son decisiones:

| Limitante | Fase A | Fase T | Fase R | Taper |
|-----------|--------|--------|--------|-------|
| Aeróbico central | Fondo largo Z2 (el más largo posible) | Fondo medio Z2 + toques Z4 | Fondo corto Z2 | Mantener frecuencia, bajar volumen |
| Umbral | Sweet spot Z3-Z4 progresivo | Intervalos Z4 (4×8', 3×12') | Z2 suave | 1-2 sesiones cortas Z4 |
| Neuromuscular | Strides, cuestas cortas | Series cortas Z5 (5×1000m) | Descanso | Activaciones Z5 cortas |
| Anaeróbico | No priorizar | Repeticiones Z6 (8×400m) | Descanso | No |
| Recuperación | DESCANSO | Reducir carga 30% | DESCANSO total | Natural del taper |

### PILAR 3 — Validación con Digital Twins

Antes de aplicar una prescripción a un atleta real, NOAH la prueba en un twin
con perfil similar y verifica:
- ¿Llega más rápido el día de la carrera?
- ¿Sin lesión?
- ¿Con TSB positivo (fresco)?

Los twins NO son para jugar con números. Son para tomar decisiones con evidencia.

---

## DIGITAL TWINS — 3 TIPOS

### Tipo 1: Clones de atletas reales
Toman el historial real (Jimena, Rodrigo, Silvina) semana por semana y comparan:
"Esta semana hiciste X, pero si hubieras hecho Y, habrías llegado mejor."
Sirven para APRENDER de la realidad y calibrar el modelo.

### Tipo 2: Perfiles elite como techo
Cómo entrena un ganador de Ironman, un campeón olímpico de tri, un sub-3 maratón,
un ganador de Río Pinto. Con sesiones reales, no porcentajes.
Desde ese techo, bajar a la realidad de cada atleta amateur.
Sirven para SABER qué es lo ideal.

### Tipo 3: Exploración por perfil × carrera × fase
Para cada combinación de perfil (edad, experiencia, horas disponibles, respuesta
individual) × carrera (5K a Ironman) × fase (A/T/R/Taper), explorar qué
entrenamiento produce el mejor día de carrera.
Sirven para DESCUBRIR el óptimo.

---

## CIENCIA: TODO CALCULADO, NADA ESTIMADO

Cada parámetro del modelo debe tener:
1. Referencia bibliográfica (paper, autor, año)
2. Valor exacto publicado (no inventado)
3. Contexto de validación (en qué población se midió)
4. Limitaciones conocidas

Ejemplo correcto:
```
tau_adaptacion_aerobico_central = 56 días
# Coyle et al. 1988, "Time course of loss of adaptations after stopping
# prolonged intense endurance training"
# Medido en: ciclistas entrenados (VO2max > 60 ml/kg/min)
# Nota: puede ser mayor en atletas recreacionales
```

Ejemplo incorrecto:
```
factor_adaptacion = 0.0005  # "parece que funciona bien"
```

---

## CONTEXTO DEL ATLETA — TODO IMPORTA

NOAH entiende que el atleta es una persona, no una máquina:

- Edad (modifica tasa de recuperación, riesgo, respuesta)
- Sexo (diferencias hormonales, de recuperación, de respuesta)
- Experiencia deportiva (años, disciplinas previas)
- Tiempo disponible (horas/semana reales, no ideales)
- Trabajo (sedentario, activo, turnos — afecta fatiga, sueño)
- Sueño (horas, calidad — es la variable #1 de recuperación)
- Nutrición (bien alimentado vs deficiente — afecta glucógeno, adaptación)
- Estrés (laboral, personal — compite por las mismas vías de recuperación)
- Historial de lesiones (zonas vulnerables)
- Biotipo (peso, composición corporal)
- Carrera objetivo (distancia, fecha, prioridad)
- Fase actual (A/T/R/Taper)

---

## DECISIÓN MÁS VALIOSA: "NO ENTRENES"

NOAH sabe que a veces la mejor prescripción es descansar.

Condiciones para prescribir descanso (no reducir carga, DESCANSO):
- Hanna Life < 25 sostenido 3+ días
- HRV cayendo + CV bajo (overreaching no funcional, Plews 2013)
- ACWR > 1.5 sostenido 3+ días (Gabbett 2016)
- Daño muscular alto + sueño < 6h
- El atleta viene de enfermedad o lesión

---

## ROADMAP DE IMPLEMENTACIÓN

### Fase 1: Modelo de sistemas fisiológicos separados
- Reescribir el twin con 5 sistemas independientes
- Cada sesión impacta cada sistema distinto
- Valores de papers reales (buscar, investigar, documentar)

### Fase 2: Perfiles elite como baseline
- Documentar planes de entrenamiento publicados de:
  - Ironman elite (Frodeno, Lange)
  - Triatlón olímpico (Brownlee, Mola)
  - Maratón sub-3 (Kipchoge training, Pfitzinger)
  - Ciclismo pro (Sky/Ineos, Coggan)
  - MTB (Schurter, Avancini)
- Codificar como baselines del twin

### Fase 3: Diagnóstico de limitantes
- Función que mira los datos del atleta y dice cuál sistema es el débil
- Conectar con el vector semanal existente

### Fase 4: Prescripción por solución
- Reemplazar patrones_sesion.py para que prescriba según limitante
- No templates fijos — decisiones basadas en diagnóstico

### Fase 5: Análisis semanal "hiciste vs óptimo"
- Tomar historial real, comparar con lo que el twin dice que era mejor
- Mostrar en dashboard del coach con explicaciones claras

### Fase 6: Exploración masiva
- Correr miles de combinaciones por perfil × carrera × fase
- Construir el mapa de estrategias óptimas
- Conectar al optimizer

---

## BIBLIOGRAFÍA BASE (a expandir con papers específicos)

- Banister 1975 — Fitness-Fatigue Model
- Coyle 1988 — Time course of detraining adaptations
- Holloszy 1967 — Mitochondrial adaptations to endurance training
- Billat 2001 — Interval training at VO2max
- Paavolainen 1999 — Neuromuscular characteristics and running economy
- Tabata 1996 — High-intensity intermittent training
- Seiler 2010 — Training intensity distribution
- Stöggl & Sperlich 2014 — Polarized vs pyramidal vs threshold
- Mujika 2003/2010 — Taper and competition
- Bosquet 2007 — Meta-analysis of taper
- Gabbett 2016 — ACWR and injury risk
- Plews 2013 — HRV monitoring in athletes
- Buchheit 2014 — HRV practical applications
- Foster 1998 — Monotony and strain
- Romijn 1993 — Substrate utilization during exercise
- Hickson 1980 — Concurrent strength and endurance training interference
- Bouchard 1999 — HERITAGE study, individual variation
- Impellizzeri 2005 — HR-power relationship stability
- Pfitzinger — Advanced Marathoning (plans)
- Coggan & Allen — Training and Racing with a Power Meter
- Friel — The Triathlete's Training Bible

---

## DOSIFICACION — EL DIFERENCIAL DE NOAH

No es "hacé Z4". Es la dosificación exacta:
- Número de intervalos
- Duración de cada intervalo
- Intensidad exacta (potencia/pace, no solo "zona")
- Duración de la pausa
- Intensidad de la pausa (activa/pasiva)
- Volumen total de la sesión
- Continuo vs intervalado
- Progresivo vs constante

Cada dosificación produce un efecto fisiológico distinto:
- 4×3' Z5 rec 2' → neuromuscular + anaeróbico (VO2max)
- 2×10' Z4 rec 5' → umbral (FTP/pace)
- 1×40' Z3 continuo → aeróbico periférico (eficiencia)
- 8×400m Z6 rec 3' → tolerancia lactato (W'bal)

NOAH debe encontrar LA dosificación óptima para cada combinación de:
perfil × fase × limitante × carrera × estado del día

El laboratorio de twins explora miles de combinaciones de dosificación
y construye una base de conocimiento: "para este perfil en esta situación,
esta dosificación produce el mejor resultado".

Los atletas reales validan: si NOAH prescribió 4×4' Z4 y funcionó,
refuerza esa dosificación para ese perfil. Si no funcionó, ajusta.

## DOS CAMINOS QUE SE ENCUENTRAN

### Camino 1 — De abajo para arriba (atletas reales)
NOAH analiza lo que el atleta hizo, cómo respondió, qué funcionó.
Con ML sobre datos reales, aprende la respuesta individual.
Mejora la prescripción semana a semana.

### Camino 2 — De arriba para abajo (laboratorio twins)
Partiendo de planes elite publicados (Seiler, Mujika, Coggan),
explorar variaciones de dosificación para cada perfil × carrera.
Descubrir combinaciones que nadie probó.
Encontrar el TECHO de rendimiento para cada tipo de atleta.

### Donde se encuentran
Cuando NOAH prescribe para Jimena real:
- Sabe el IDEAL (del laboratorio)
- Sabe lo que Jimena PUEDE y CÓMO responde (del ML real)
- Adapta la dosificación ideal a su realidad
- Resultado: la mejor sesión posible para ella HOY

## NOTA PARA CHATS FUTUROS

Este documento es el cerebro de NOAH. Antes de codear cualquier cosa,
leer esto. Todo cambio debe ser consistente con esta visión. Si algo
contradice lo de acá, hay que discutirlo primero, no parchear.

El objetivo final: que cuando NOAH prescriba un entrenamiento, no esté
adivinando. SEPA que es el mejor posible para ese atleta en ese momento
para que llegue lo más rápido posible el día de la carrera.
