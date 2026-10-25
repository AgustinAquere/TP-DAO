"""Datos de ejemplo para probar la aplicación y los reportes.

Todo se carga a través de los servicios (no con INSERT directos), así los datos respetan las
mismas reglas de negocio que la interfaz: esquema de vacunas, turnos sin superposición,
ciclo de vida de muestras y remitos, estrategias de tarifa, etc.
"""
import random
from datetime import date, datetime, time, timedelta

from app.dominio.atencion import Tratamiento
from app.dominio.derivacion import TipoAnalisis
from app.dominio.enums import Prioridad, Sexo, TipoAtencion, TipoItem, TipoMuestra
from app.dominio.envio import Conservadora
from app.dominio.excepciones import ErrorNegocio
from app.dominio.facturacion import ItemComprobante, ServicioClinico
from app.dominio.laboratorio import DetalleResultado
from app.dominio.mascota import Especie
from app.dominio.organizaciones import Clinica, LaboratorioCentral, Transportista
from app.dominio.personas import Bioquimico, Veterinario
from app.dominio.vacunas import Vacuna, VacunaObligatoria
from app.servicios.atencion_service import SolicitudDerivacion
from app.servicios.contenedor import Servicios
from app.utils import fechas

DIAS_DE_HISTORIA = 75

MOTIVOS = {
    TipoAtencion.CONSULTA: [
        ("Vómitos y decaimiento", "Gastroenteritis aguda", ["HEMO", "BIOQ"]),
        ("Diarrea con sangre", "Sospecha de parvovirosis", ["COPRO", "PCRP"]),
        ("Prurito intenso", "Dermatitis alérgica", ["CULT"]),
        ("Pérdida de apetito", "Enfermedad periodontal", ["HEMO", "BIOQ"]),
        ("Cojera de miembro posterior", "Esguince leve", []),
        ("Tos persistente", "Traqueobronquitis", ["HEMO", "CULT"]),
        ("Aumento de sed y de orina", "Sospecha de enfermedad renal", ["BIOQ", "ORIN", "HEMO"]),
        ("Nódulo en la piel", "Neoformación cutánea a estudiar", ["HISTO", "HEMO"]),
        ("Pérdida de peso", "Sospecha de hipertiroidismo", ["T4", "BIOQ"]),
    ],
    TipoAtencion.CONTROL: [
        ("Control anual y vacunación", "Paciente sano", ["HEMO", "BIOQ"]),
        ("Control postquirúrgico", "Evolución favorable", []),
        ("Control de tratamiento dermatológico", "Mejoría parcial", []),
        ("Control de peso", "Sobrepeso leve", []),
        ("Control de función renal", "Enfermedad renal estable", ["BIOQ", "ORIN"]),
    ],
    TipoAtencion.URGENCIA: [
        ("Traumatismo por atropello", "Politraumatismo", ["HEMO", "BIOQ"]),
        ("Ingesta de sustancia tóxica", "Intoxicación", ["HEMO", "BIOQ"]),
        ("Dificultad respiratoria", "Disnea aguda", ["HEMO"]),
        ("Convulsiones", "Síndrome convulsivo", ["HEMO", "BIOQ"]),
    ],
}

TRATAMIENTOS = [
    ("Antibioticoterapia", "Amoxicilina + ácido clavulánico", "12,5 mg/kg", "cada 12 h", 7),
    ("Antiinflamatorio", "Meloxicam", "0,1 mg/kg", "cada 24 h", 5),
    ("Desparasitación interna", "Praziquantel + pirantel", "1 comp. cada 10 kg", "dosis única", 0),
    ("Tratamiento dermatológico", "Shampoo de clorhexidina 2 %", "baño completo", "2 veces por semana", 28),
    ("Protector gástrico", "Omeprazol", "1 mg/kg", "cada 24 h", 10),
    ("Fluidoterapia", "Ringer lactato", "50 ml/kg/día", "infusión continua", 2),
    ("Control de pulgas y garrapatas", "Fluralaner", "1 comprimido", "cada 12 semanas", 84),
    ("Dieta terapéutica renal", "Alimento renal", "según peso", "diaria", None),
]


class _Sembrador:
    def __init__(self, servicios: Servicios, ahora: datetime, semilla: int = 2026):
        self.s = servicios
        self.ahora = ahora
        self.hoy = ahora.date()
        self.rnd = random.Random(semilla)
        self.nro_remito = 0

    # --- Catálogos ---------------------------------------------------------------------
    def _guardar(self, entidad: str, *objetos):
        for objeto in objetos:
            self.s.catalogos.guardar(entidad, objeto)
        return objetos

    def catalogos(self) -> None:
        self.clinicas = self._guardar(
            "clinica",
            Clinica(nombre="Clínica Veterinaria Centro", direccion="Av. Colón 1250, Córdoba", cuit="30-71234567-1",
                    telefono="351 422-1100"),
            Clinica(nombre="Clínica Veterinaria Cerro", direccion="Av. Rafael Núñez 4560, Córdoba",
                    cuit="30-71234568-2", telefono="351 481-2200"),
            Clinica(nombre="Clínica Veterinaria Nueva Córdoba", direccion="Bv. Illia 380, Córdoba",
                    cuit="30-71234569-3", telefono="351 468-3300"))
        centro, cerro, nueva = (c.id for c in self.clinicas)
        self.laboratorio, = self._guardar("laboratorio", LaboratorioCentral(
            nombre="Laboratorio Central de Diagnóstico Veterinario", direccion="Av. Vélez Sarsfield 1600, Córdoba",
            telefono="351 433-9000"))
        self.bioquimicos = self._guardar(
            "bioquimico",
            Bioquimico(dni="27456123", nombre="Lucía", apellido="Ferreyra", matricula="MP 4521",
                       email="lferreyra@labcentral.com.ar", id_laboratorio=self.laboratorio.id),
            Bioquimico(dni="30987456", nombre="Martín", apellido="Quiroga", matricula="MP 4876",
                       email="mquiroga@labcentral.com.ar", id_laboratorio=self.laboratorio.id))
        self.veterinarios = self._guardar(
            "veterinario",
            Veterinario(dni="25111222", nombre="Carolina", apellido="Méndez", matricula="MV 2231",
                        especialidad="Clínica general", telefono="351 555-0101", ids_clinicas=[centro, nueva]),
            Veterinario(dni="26333444", nombre="Javier", apellido="Sosa", matricula="MV 2456",
                        especialidad="Cirugía", telefono="351 555-0102", ids_clinicas=[centro]),
            Veterinario(dni="28555666", nombre="Florencia", apellido="Paz", matricula="MV 2789",
                        especialidad="Dermatología", telefono="351 555-0103", ids_clinicas=[cerro]),
            Veterinario(dni="29777888", nombre="Diego", apellido="Arias", matricula="MV 3012",
                        especialidad="Medicina felina", telefono="351 555-0104", ids_clinicas=[cerro, nueva]),
            Veterinario(dni="31999000", nombre="Valentina", apellido="Ruiz", matricula="MV 3157",
                        especialidad="Emergentología", telefono="351 555-0105", ids_clinicas=[centro, cerro, nueva]))
        canino, felino, conejo = self._guardar("especie", Especie(nombre="Canino"), Especie(nombre="Felino"),
                                               Especie(nombre="Conejo"))
        self.especies = {"Canino": canino.id, "Felino": felino.id, "Conejo": conejo.id}
        sextuple, rabia, triple, leucemia, _tos, mixo = self._guardar(
            "vacuna",
            Vacuna(nombre="Séxtuple canina", laboratorio_fabricante="Zoetis"),
            Vacuna(nombre="Antirrábica", laboratorio_fabricante="Biogénesis Bagó"),
            Vacuna(nombre="Triple felina", laboratorio_fabricante="MSD Salud Animal"),
            Vacuna(nombre="Leucemia felina", laboratorio_fabricante="Boehringer Ingelheim"),
            Vacuna(nombre="Tos de las perreras", laboratorio_fabricante="Zoetis"),
            Vacuna(nombre="Mixomatosis", laboratorio_fabricante="Laboratorio Ovejero"))
        self._guardar(
            "esquema",
            VacunaObligatoria(id_especie=canino.id, id_vacuna=sextuple.id, edad_minima_semanas=6,
                              frecuencia_refuerzo_dias=365),
            VacunaObligatoria(id_especie=canino.id, id_vacuna=rabia.id, edad_minima_semanas=12,
                              frecuencia_refuerzo_dias=365),
            VacunaObligatoria(id_especie=felino.id, id_vacuna=triple.id, edad_minima_semanas=8,
                              frecuencia_refuerzo_dias=365),
            VacunaObligatoria(id_especie=felino.id, id_vacuna=rabia.id, edad_minima_semanas=12,
                              frecuencia_refuerzo_dias=365),
            VacunaObligatoria(id_especie=felino.id, id_vacuna=leucemia.id, edad_minima_semanas=9,
                              frecuencia_refuerzo_dias=365),
            VacunaObligatoria(id_especie=conejo.id, id_vacuna=mixo.id, edad_minima_semanas=8,
                              frecuencia_refuerzo_dias=180))
        analisis = self._guardar(
            "tipo_analisis",
            TipoAnalisis(codigo="HEMO", nombre="Hemograma completo", tipo_muestra_requerida=TipoMuestra.SANGRE,
                         temp_min_c=2, temp_max_c=8, horas_max_viabilidad=24, precio=14500),
            TipoAnalisis(codigo="BIOQ", nombre="Perfil bioquímico", tipo_muestra_requerida=TipoMuestra.SUERO,
                         temp_min_c=2, temp_max_c=8, horas_max_viabilidad=48, precio=21000),
            TipoAnalisis(codigo="T4", nombre="Tiroxina (T4 total)", tipo_muestra_requerida=TipoMuestra.SUERO,
                         temp_min_c=2, temp_max_c=8, horas_max_viabilidad=72, precio=16500),
            TipoAnalisis(codigo="ORIN", nombre="Urianálisis completo", tipo_muestra_requerida=TipoMuestra.ORINA,
                         temp_min_c=2, temp_max_c=8, horas_max_viabilidad=12, precio=9800),
            TipoAnalisis(codigo="COPRO", nombre="Coproparasitológico", tipo_muestra_requerida=TipoMuestra.MATERIA_FECAL,
                         temp_min_c=2, temp_max_c=8, horas_max_viabilidad=48, precio=8200),
            TipoAnalisis(codigo="PCRP", nombre="PCR parvovirus canino", tipo_muestra_requerida=TipoMuestra.MATERIA_FECAL,
                         temp_min_c=2, temp_max_c=8, horas_max_viabilidad=48, precio=27000),
            TipoAnalisis(codigo="CULT", nombre="Cultivo y antibiograma", tipo_muestra_requerida=TipoMuestra.HISOPADO,
                         temp_min_c=2, temp_max_c=8, horas_max_viabilidad=24, precio=23500),
            TipoAnalisis(codigo="HISTO", nombre="Histopatología", tipo_muestra_requerida=TipoMuestra.TEJIDO,
                         temp_min_c=15, temp_max_c=25, horas_max_viabilidad=168, precio=38000))
        self.analisis = {a.codigo: a.id for a in analisis}
        self._guardar(
            "servicio",
            ServicioClinico(codigo="CONS", nombre="Consulta clínica", precio_base=18000),
            ServicioClinico(codigo="CTRL", nombre="Control de seguimiento", precio_base=12000),
            ServicioClinico(codigo="URG", nombre="Atención de urgencia", precio_base=30000),
            ServicioClinico(codigo="ECO", nombre="Ecografía abdominal", precio_base=28000),
            ServicioClinico(codigo="CUR", nombre="Curación y vendaje", precio_base=9500))
        self._guardar(
            "conservadora",
            Conservadora(codigo="CONS-01", capacidad=6, temp_min_c=2, temp_max_c=8),
            Conservadora(codigo="CONS-02", capacidad=10, temp_min_c=2, temp_max_c=8),
            Conservadora(codigo="CONS-03", capacidad=8, temp_min_c=3, temp_max_c=7),
            Conservadora(codigo="CONS-04", capacidad=4, temp_min_c=15, temp_max_c=25),
            Conservadora(codigo="CONS-05", capacidad=6, temp_min_c=2, temp_max_c=8),
            Conservadora(codigo="CONS-06", capacidad=6, temp_min_c=2, temp_max_c=8))
        self.transportistas = self._guardar(
            "transportista",
            Transportista(razon_social="BioLogística Córdoba S.A.", cuit="30-70811223-4", telefono="351 470-1000",
                          patente_vehiculo="AB123CD"),
            Transportista(razon_social="Frío Express SRL", cuit="30-70922334-5", telefono="351 470-2000",
                          patente_vehiculo="AC456EF"),
            Transportista(razon_social="Mensajería Veterinaria del Centro", cuit="20-28765432-1",
                          telefono="351 470-3000", patente_vehiculo="AD789GH"))

    # --- Clientes y mascotas --------------------------------------------------------------------
    def clientes_y_mascotas(self) -> None:
        clientes = [
            ("30123456", "Ana", "García", "351 611-2233", "ana.garcia@gmail.com", "Obispo Trejo 450"),
            ("28456789", "Pablo", "Fernández", "351 622-3344", "pfernandez@hotmail.com", "Av. Hipólito Yrigoyen 120"),
            ("33789012", "María José", "López", "351 633-4455", "mjlopez@gmail.com", "Rondeau 870"),
            ("25678123", "Ricardo", "Martínez", "351 644-5566", None, "Av. Sabattini 2300"),
            ("35234567", "Sofía", "Romero", "351 655-6677", "sofi.romero@gmail.com", "Belgrano 1020"),
            ("29345678", "Gustavo", "Torres", "351 666-7788", "gtorres@yahoo.com.ar", "Duarte Quirós 3400"),
            ("31456789", "Camila", "Díaz", "351 677-8899", "camidiaz@gmail.com", "Independencia 560"),
            ("27567890", "Hernán", "Gómez", "351 688-9900", None, "Av. Recta Martinoli 7100"),
            ("34678901", "Julieta", "Acosta", "351 699-0011", "juli.acosta@gmail.com", "Chacabuco 890"),
            ("26789012", "Marcelo", "Benítez", "351 600-1122", "mbenitez@gmail.com", "Av. Fuerza Aérea 2200"),
            ("36890123", "Agustina", "Herrera", "351 601-2233", "agus.herrera@outlook.com", "Ituzaingó 1500"),
            ("32901234", "Federico", "Molina", "351 602-3344", "fede.molina@gmail.com", "Av. Castro Barros 640"),
            ("24012345", "Graciela", "Castro", "351 603-4455", None, "Santa Rosa 2100"),
            ("37123456", "Tomás", "Vega", "351 604-5566", "tomas.vega@gmail.com", "Laprida 330"),
        ]
        ids = [self.s.clientes.alta(dni=dni, nombre=nombre, apellido=apellido, telefono=tel, email=mail,
                                    direccion=f"{dir_}, Córdoba",
                                    fecha_alta=self.hoy - timedelta(days=self.rnd.randint(900, 1500))).id
               for dni, nombre, apellido, tel, mail, dir_ in clientes]
        hace = lambda dias: self.hoy - timedelta(days=dias)
        mascotas = [  # (índice cliente, especie, nombre, raza, sexo, fecha de nacimiento, peso)
            (0, "Canino", "Luna", "Labrador retriever", Sexo.HEMBRA, hace(1460), 27.5),
            (0, "Felino", "Michi", "Europeo común", Sexo.MACHO, hace(2200), 4.8),
            (1, "Canino", "Rocco", "Ovejero alemán", Sexo.MACHO, hace(2900), 34.0),
            (2, "Canino", "Kira", "Caniche toy", Sexo.HEMBRA, hace(70), 1.6),
            (3, "Canino", "Toby", "Beagle", Sexo.MACHO, hace(3300), 14.2),
            (4, "Felino", "Nala", "Siamés", Sexo.HEMBRA, hace(420), 3.9),
            (4, "Conejo", "Copito", "Mini lop", Sexo.MACHO, hace(500), 1.9),
            (5, "Canino", "Bruno", "Bulldog francés", Sexo.MACHO, hace(1100), 12.0),
            (6, "Felino", "Simba", "Maine coon", Sexo.MACHO, hace(150), 3.2),
            (7, "Canino", "Negra", "Mestiza", Sexo.HEMBRA, hace(3800), 18.5),
            (8, "Canino", "Coco", "Golden retriever", Sexo.MACHO, hace(800), 31.0),
            (8, "Felino", "Mora", "Persa", Sexo.HEMBRA, hace(2600), 4.1),
            (9, "Canino", "Thor", "Rottweiler", Sexo.MACHO, hace(1900), 42.0),
            (10, "Felino", "Olivia", "Europeo común", Sexo.HEMBRA, hace(95), 1.4),
            (10, "Canino", "Pipa", "Jack Russell terrier", Sexo.HEMBRA, hace(1300), 6.8),
            (11, "Canino", "Lola", "Border collie", Sexo.HEMBRA, hace(600), 17.3),
            (12, "Felino", "Garfield", "Exótico de pelo corto", Sexo.MACHO, hace(4100), 6.2),
            (12, "Canino", "Chispa", "Schnauzer miniatura", Sexo.HEMBRA, hace(2400), 7.5),
            (13, "Canino", "Max", "Mestizo", Sexo.MACHO, hace(250), 9.0),
            (13, "Conejo", "Tambor", "Holland lop", Sexo.MACHO, hace(1000), 1.7),
        ]
        self.mascotas = []
        for i, especie, nombre, raza, sexo, nacimiento, peso in mascotas:
            apertura = max(nacimiento, self.hoy - timedelta(days=self.rnd.randint(430, 900)))
            mascota = self.s.mascotas.alta(ids[i], apertura, id_especie=self.especies[especie], nombre=nombre, raza=raza,
                                           sexo=sexo, fecha_nacimiento=nacimiento, peso_kg=peso,
                                           microchip=f"98510{self.rnd.randint(10 ** 9, 10 ** 10 - 1)}")
            self.mascotas.append(mascota)

    # --- Actividad clínica -------------------------------------------------------------------
    def historia_previa(self) -> None:
        """Control anual con vacunación hace aproximadamente un año: algunos refuerzos ya vencieron."""
        for mascota in self.mascotas:
            dia = self.hoy - timedelta(days=self.rnd.randint(300, 420))
            if mascota.fecha_nacimiento > dia - timedelta(weeks=12) or self.rnd.random() < 0.2:
                continue
            veterinario = self.rnd.choice(self.veterinarios)
            momento = datetime.combine(dia, time(self.rnd.randint(9, 18), 0))
            pendientes = self.s.atenciones.vacunas_pendientes(mascota.id, dia)
            atencion = self.s.atenciones.registrar(
                id_mascota=mascota.id, id_veterinario=veterinario.id, id_clinica=veterinario.ids_clinicas[0],
                tipo=TipoAtencion.CONTROL, motivo="Control anual y vacunación", diagnostico="Paciente sano",
                fecha_hora=momento, vacunas=[(vo.id_vacuna, f"L{self.rnd.randint(10000, 99999)}") for vo in pendientes],
                confirmar_esquema_incompleto=True)
            self._facturar(atencion)

    def _momento(self, dia: date, tipo: TipoAtencion) -> datetime:
        if tipo == TipoAtencion.URGENCIA and self.rnd.random() < 0.4:
            return datetime.combine(dia, time(self.rnd.choice([21, 22, 23]), self.rnd.choice([0, 15, 40])))
        return datetime.combine(dia, time(self.rnd.randint(9, 18), self.rnd.choice([0, 30])))

    def actividad(self) -> None:
        atenciones = []
        dias = sorted(self.hoy - timedelta(days=self.rnd.randint(1, DIAS_DE_HISTORIA)) for _ in range(46))
        for dia in dias:
            tipo = self.rnd.choices(list(MOTIVOS), weights=[5, 3, 2])[0]
            momento = self._momento(dia, tipo)
            if momento > self.ahora - timedelta(hours=2):
                continue
            atencion = self._registrar_atencion(tipo, momento)
            if atencion:
                atenciones.append(atencion)
        # Las atenciones de los últimos días quedan sin facturar para poder probar el proceso
        for atencion in atenciones:
            if atencion.fecha_hora.date() < self.hoy - timedelta(days=2):
                self._facturar(atencion)

    def _registrar_atencion(self, tipo: TipoAtencion, momento: datetime):
        mascota = self.rnd.choice(self.mascotas)
        veterinario = self.rnd.choice(self.veterinarios)
        id_clinica = self.rnd.choice(veterinario.ids_clinicas)
        motivo, diagnostico, analisis = self.rnd.choice(MOTIVOS[tipo])
        id_turno = None
        if tipo != TipoAtencion.URGENCIA and self.rnd.random() < 0.45:
            try:
                id_turno = self.s.turnos.reservar(veterinario.id, mascota.id, id_clinica, momento, 30,
                                                  ahora=momento - timedelta(days=3)).id
            except ErrorNegocio:
                id_turno = None
        pendientes = self.s.atenciones.vacunas_pendientes(mascota.id, momento.date())
        vacunas = [(vo.id_vacuna, f"L{self.rnd.randint(10000, 99999)}") for vo in pendientes
                   if self.rnd.random() < 0.7]
        tratamientos = []
        if self.rnd.random() < 0.55:
            descripcion, medicamento, dosis, frecuencia, dias = self.rnd.choice(TRATAMIENTOS)
            tratamientos.append(Tratamiento(descripcion=descripcion, medicamento=medicamento, dosis=dosis,
                                            frecuencia=frecuencia, fecha_inicio=momento.date(),
                                            fecha_fin=None if dias is None else momento.date() + timedelta(days=dias)))
        derivacion = None
        if analisis and self.rnd.random() < 0.6:
            elegidos = analisis if self.rnd.random() < 0.6 else analisis[:1]
            derivacion = SolicitudDerivacion(
                id_laboratorio=self.laboratorio.id, ids_tipo_analisis=[self.analisis[c] for c in elegidos],
                prioridad=Prioridad.URGENTE if tipo == TipoAtencion.URGENCIA else Prioridad.NORMAL,
                indicaciones=f"{diagnostico}. Se solicita evaluación.",
                volumenes={TipoMuestra.SANGRE: 3.0, TipoMuestra.SUERO: 2.0, TipoMuestra.ORINA: 10.0})
        atencion = self.s.atenciones.registrar(
            id_mascota=mascota.id, id_veterinario=veterinario.id, id_clinica=id_clinica, tipo=tipo, motivo=motivo,
            fecha_hora=momento, id_turno=id_turno, anamnesis=f"Propietario refiere: {motivo.lower()}.",
            diagnostico=diagnostico, peso_registrado_kg=round(mascota.peso_kg * self.rnd.uniform(0.95, 1.05), 1),
            tratamientos=tratamientos, vacunas=vacunas, derivacion=derivacion, confirmar_esquema_incompleto=True)
        for orden in atencion.ordenes:
            self._circuito_de_muestras(orden.id_atencion, id_clinica, veterinario, momento)
        return atencion

    # --- Empaquetado, envío, recepción y resultados ---------------------------------------------
    def _circuito_de_muestras(self, id_atencion: int, id_clinica: int, veterinario, extraccion: datetime) -> None:
        ordenes = {o.numero for o in self.s.atenciones.obtener(id_atencion).ordenes}
        pendientes = [m for m in self.s.derivaciones.muestras_pendientes(id_clinica) if m["orden"] in ordenes]
        grupos = {}
        for muestra in pendientes:  # las muestras con distinto rango de conservación viajan en conservadoras distintas
            grupos.setdefault((muestra["temp_min_requerida"], muestra["temp_max_requerida"]), []).append(muestra["id_muestra"])
        for (minimo, maximo), ids in grupos.items():
            conservadora = next((c for c in self.s.derivaciones.conservadoras_disponibles()
                                 if minimo <= c.temp_min_c and c.temp_max_c <= maximo and c.capacidad >= len(ids)), None)
            momento = extraccion + timedelta(minutes=self.rnd.randint(20, 50))
            if conservadora is None or momento > self.ahora:
                continue
            remito = self.s.derivaciones.armar_remito(ids, conservadora.id, id_clinica, momento)
            self.nro_remito += 1
            self._avanzar_remito(remito.id, veterinario.nombre_completo(), momento, self.nro_remito, conservadora)

    def _avanzar_remito(self, id_remito: int, responsable: str, inicio: datetime, numero: int,
                        conservadora: Conservadora) -> None:
        """Avanza el remito por su ciclo de vida mientras las fechas no superen el momento actual.

        Algunos remitos simulan fallas de transporte para los reportes: precinto roto,
        cadena de frío interrumpida o demoras que vencen la viabilidad de las muestras.
        """
        falla = {4: "precinto", 9: "temperatura", 14: "demora", 19: "temperatura"}.get(numero)
        # Temperatura dentro del rango que mantiene la conservadora (salvo la falla de cadena de frío)
        temperatura = lambda: round(self.rnd.uniform(conservadora.temp_min_c + 0.5, conservadora.temp_max_c - 0.5), 1)
        precintado = inicio + timedelta(minutes=30)
        if precintado > self.ahora:
            return
        self.s.derivaciones.precintar(id_remito, responsable, fecha_hora=precintado)
        salida = precintado + timedelta(minutes=self.rnd.randint(30, 90))
        if salida > self.ahora:
            return
        transportista = self.rnd.choice(self.transportistas)
        self.s.derivaciones.despachar(id_remito, transportista.id, responsable, temperatura_salida=temperatura(),
                                      fecha_hora=salida)
        llegada = salida + timedelta(hours=self.rnd.uniform(2.5, 7) if falla != "demora" else 27)
        if self.rnd.random() < 0.35 or falla == "demora":  # cambio de transportista en un centro de distribución
            posta = salida + (llegada - salida) / 2
            if posta > self.ahora:
                return
            self.s.derivaciones.cerrar_tramo(id_remito, posta, "Centro de distribución Ruta 9", temperatura())
            otro = self.rnd.choice([t for t in self.transportistas if t.id != transportista.id])
            self.s.derivaciones.registrar_tramo(id_remito, otro.id, "Centro de distribución Ruta 9",
                                                self.laboratorio.nombre, posta + timedelta(minutes=20),
                                                "Operador de logística", temperatura())
        if llegada > self.ahora:
            return
        bioquimico = self.rnd.choice(self.bioquimicos)
        arribo = 11.5 if falla == "temperatura" else temperatura()
        remito = self.s.laboratorio.registrar_recepcion(
            id_remito, bioquimico.id, precinto_intacto=falla != "precinto", temperatura_arribo=arribo,
            observacion="El precinto presenta signos de apertura." if falla == "precinto" else None, fecha_hora=llegada)
        self._cargar_resultados(remito, llegada)

    def _cargar_resultados(self, remito, recepcion: datetime) -> None:
        momento = recepcion + timedelta(hours=self.rnd.uniform(3, 20))
        for pendiente in self.s.laboratorio.analisis_pendientes(self.laboratorio.id):
            if pendiente["muestra"] not in {m.codigo for m in remito.muestras}:
                continue
            if momento > self.ahora - timedelta(hours=6):
                return  # los más recientes quedan pendientes de resultado
            detalles = self.s.laboratorio.plantilla_resultado(pendiente["codigo"])
            for detalle in detalles:
                detalle.valor = self._valor_simulado(detalle)
            fuera = [d for d in detalles if d.fuera_de_rango()]
            self.s.laboratorio.registrar_resultado(
                pendiente["id_analisis_solicitado"], self.rnd.choice(self.bioquimicos).id, detalles,
                interpretacion="Valores dentro de los rangos de referencia." if not fuera
                else f"Se observan alteraciones en: {', '.join(d.parametro for d in fuera)}.",
                fecha_hora=momento)
            momento += timedelta(minutes=self.rnd.randint(20, 90))

    def _valor_simulado(self, detalle: DetalleResultado) -> float:
        minimo, maximo = detalle.valor_ref_min or 0.0, detalle.valor_ref_max or 0.0
        if maximo == 0:
            return 0.0 if self.rnd.random() < 0.75 else float(self.rnd.randint(50, 400))
        valor = self.rnd.uniform(minimo * 0.85, maximo * 1.15)
        return round(valor, 3 if maximo < 2 else 1)

    # --- Circuitos en curso -------------------------------------------------------------------
    def escenarios_en_curso(self) -> None:
        """Atenciones recientes que dejan cada etapa del circuito pendiente, para probarla desde la interfaz."""
        casos = [  # (horas atrás, análisis, etapa hasta la que se avanza)
            (3, ["HISTO"], None), (5, ["HEMO", "CULT"], None), (26, ["COPRO"], "preparacion"),
            (24, ["BIOQ", "T4"], "precintado"), (8, ["HEMO", "BIOQ"], "transito"),
            (30, ["HEMO", "BIOQ", "ORIN"], "recibido"),
        ]
        for i, (horas, codigos, etapa) in enumerate(casos):
            momento = (self.ahora - timedelta(hours=horas)).replace(second=0)
            tipo = TipoAtencion.CONSULTA if 8 <= momento.hour < 19 else TipoAtencion.URGENCIA
            veterinario = self.veterinarios[i % len(self.veterinarios)]
            id_clinica = veterinario.ids_clinicas[0]
            motivo, diagnostico, _ = next((m for m in MOTIVOS[tipo] if set(codigos) <= set(m[2])), MOTIVOS[tipo][0])
            atencion = self.s.atenciones.registrar(
                id_mascota=self.mascotas[(i * 3) % len(self.mascotas)].id, id_veterinario=veterinario.id,
                id_clinica=id_clinica, tipo=tipo, motivo=motivo, diagnostico=diagnostico, fecha_hora=momento,
                derivacion=SolicitudDerivacion(id_laboratorio=self.laboratorio.id,
                                               ids_tipo_analisis=[self.analisis[c] for c in codigos],
                                               indicaciones=f"{diagnostico}. Se solicita evaluación."),
                confirmar_esquema_incompleto=True)
            if etapa is None:
                continue
            numeros = {o.numero for o in atencion.ordenes}
            ids = [m["id_muestra"] for m in self.s.derivaciones.muestras_pendientes(id_clinica) if m["orden"] in numeros]
            conservadora = next(c for c in self.s.derivaciones.conservadoras_disponibles()
                                if 2 <= c.temp_min_c and c.temp_max_c <= 8)
            remito = self.s.derivaciones.armar_remito(ids, conservadora.id, id_clinica, momento + timedelta(minutes=30))
            if etapa == "preparacion":
                continue
            self.s.derivaciones.precintar(remito.id, veterinario.nombre_completo(),
                                          fecha_hora=momento + timedelta(hours=1))
            if etapa == "precintado":
                continue
            self.s.derivaciones.despachar(remito.id, self.transportistas[0].id, veterinario.nombre_completo(),
                                          temperatura_salida=4.5, fecha_hora=momento + timedelta(hours=1, minutes=30))
            if etapa == "transito":
                continue
            self.s.laboratorio.registrar_recepcion(remito.id, self.bioquimicos[0].id, precinto_intacto=True,
                                                   temperatura_arribo=5.2, fecha_hora=momento + timedelta(hours=5))

    # --- Facturación -----------------------------------------------------------------------
    def _facturar(self, atencion) -> None:
        items = self.s.facturacion.items_sugeridos(atencion.id)
        if self.rnd.random() < 0.25:
            items.append(ItemComprobante(tipo=TipoItem.INSUMO, descripcion="Material descartable y jeringas",
                                         precio_unitario=1800, cantidad=self.rnd.randint(1, 3)))
        self.s.facturacion.emitir(atencion.id, items, atencion.fecha_hora + timedelta(minutes=40))

    # --- Turnos futuros ------------------------------------------------------------------------
    def turnos(self) -> None:
        for desplazamiento in range(0, 5):
            dia = self.hoy + timedelta(days=desplazamiento)
            for veterinario in self.veterinarios:
                libres = self.s.turnos.horarios_disponibles(veterinario.id, dia, 30)
                for inicio in self.rnd.sample(libres, min(len(libres), self.rnd.randint(1, 3))):
                    self.s.turnos.reservar(veterinario.id, self.rnd.choice(self.mascotas).id,
                                           self.rnd.choice(veterinario.ids_clinicas), inicio, 30)

    def cargar(self) -> None:
        self.catalogos()
        self.clientes_y_mascotas()
        self.historia_previa()
        self.actividad()
        self.escenarios_en_curso()
        self.turnos()


def cargar_datos_de_ejemplo(servicios: Servicios, ahora: datetime | None = None) -> None:
    _Sembrador(servicios, ahora or fechas.ahora()).cargar()
