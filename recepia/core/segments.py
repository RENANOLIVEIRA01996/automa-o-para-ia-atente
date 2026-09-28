"""Single source of truth for tenant-facing segment presets.

The frontend receives the resolved preset from the authenticated API. Physical
table names remain unchanged so existing tenant data and integrations survive.
"""

from copy import deepcopy


_BASE_NAV = (
    "overview",
    "agenda",
    "appointments",
    "customers",
    "services",
    "professionals",
    "conversations",
    "whatsapp",
    "hours",
    "business",
    "settings",
    "plan",
)

_NAV_ICONS = {
    "overview": "layout-dashboard",
    "agenda": "calendar-days",
    "appointments": "calendar-check",
    "customers": "users-round",
    "vehicles": "car-front",
    "services": "list-checks",
    "professionals": "users",
    "conversations": "messages-square",
    "whatsapp": "message-circle",
    "hours": "clock-3",
    "business": "building-2",
    "settings": "settings-2",
    "plan": "credit-card",
    "history": "file-clock",
    "work_orders": "clipboard-list",
    "pets": "paw-print",
    "rooms": "bed-double",
    "reservations": "calendar-range",
    "checkins": "log-in",
    "checkouts": "log-out",
}
_EXTRA_NAV = frozenset(
    {
        "vehicles",
        "work_orders",
        "pets",
        "rooms",
        "reservations",
        "checkins",
        "checkouts",
    }
)

_BASE = {
    "name": "Serviços",
    "labels": {
        "customer": "Cliente",
        "customers": "Clientes",
        "service": "Serviço",
        "services": "Serviços",
        "professional": "Profissional",
        "professionals": "Equipe",
        "appointment": "Agendamento",
        "appointments": "Agendamentos",
    },
    "dashboard": {
        "title": "Visão geral",
        "subtitle": "Acompanhe a operação da sua empresa.",
        "cards": [
            {"metric": "agendamentos_hoje", "label": "Agendamentos hoje"},
            {"metric": "proximos_agendamentos", "label": "Próximos horários"},
            {"metric": "novos_clientes_hoje", "label": "Novos clientes"},
            {"metric": "cancelamentos_hoje", "label": "Cancelamentos hoje"},
        ],
    },
    "navigation": _BASE_NAV,
    "navigation_labels": {
        "overview": "Dashboard",
        "agenda": "Agenda",
        "conversations": "Conversas",
        "whatsapp": "WhatsApp",
        "hours": "Horários",
        "business": "Empresa e IA",
        "settings": "Configurações",
        "plan": "Plano",
        "vehicles": "Veículos",
        "pets": "Pets",
        "rooms": "Quartos",
        "reservations": "Reservas",
        "work_orders": "Ordens de serviço",
        "history": "Histórico",
        "checkins": "Check-in",
        "checkouts": "Check-out",
    },
    "modules": [],
    "enabled_modules": [],
    "extra_fields": {"customer": [], "appointment": [], "business": []},
    "onboarding": {
        "title": "Prepare sua empresa para atender pelo WhatsApp",
        "customer_hint": "Cadastre seus clientes e serviços para começar.",
        "service_hint": "Adicione seu primeiro serviço com preço e duração.",
    },
    "ai": {"guidance": "Use os nomes dos serviços e os horários reais da empresa."},
    "icons": {
        "customer": "user-round",
        "service": "list-checks",
        "professional": "users",
    },
    "theme": {"accent": "#176c69"},
}

_CLINIC_CARDS = [
    {"metric": "agendamentos_hoje", "label": "Consultas hoje"},
    {"metric": "confirmados_hoje", "label": "Confirmadas"},
    {"metric": "pendentes_hoje", "label": "Pendentes"},
    {"metric": "faltas_hoje", "label": "Faltas"},
    {"metric": "proximos_agendamentos", "label": "Próximos pacientes"},
]

SEGMENT_PRESETS = {
    "CAR_WASH": {
        "name": "Lava-rápido",
        "labels": {
            "professional": "Profissional",
            "professionals": "Equipe",
            "appointment": "Lavagem",
            "appointments": "Agendamentos",
        },
        "navigation": (
            "overview",
            "agenda",
            "appointments",
            "customers",
            "vehicles",
            "services",
            "professionals",
            "conversations",
            "whatsapp",
            "hours",
            "business",
            "settings",
            "plan",
        ),
        "dashboard": {
            "title": "Operação do lava-rápido",
            "subtitle": "Lavagens, veículos e horários em um só lugar.",
            "cards": [
                {"metric": "agendamentos_hoje", "label": "Lavagens hoje"},
                {"metric": "em_andamento_hoje", "label": "Em andamento"},
                {"metric": "concluidos_hoje", "label": "Concluídas"},
                {
                    "metric": "receita_hoje",
                    "label": "Valor estimado concluído hoje",
                    "format": "currency",
                },
                {"metric": "proximos_agendamentos", "label": "Próximos horários"},
            ],
        },
        "modules": ["vehicles"],
        "enabled_modules": ["vehicles"],
        "extra_fields": {
            "customer": [],
            "appointment": [
                {"key": "vehicle_id", "label": "Veículo", "type": "entity"}
            ],
            "business": [],
        },
        "onboarding": {
            "title": "Prepare seu lava-rápido para receber agendamentos",
            "customer_hint": "Cadastre clientes e veículos.",
            "service_hint": "Cadastre uma lavagem com duração e preço.",
        },
        "ai": {
            "guidance": (
                "Antes de agendar, liste os veículos do cliente; se não houver o "
                "veículo correto, peça a placa e cadastre-o. Confirme marca e "
                "modelo quando possível. Use o vehicle_id na reserva."
            )
        },
        "icons": {
            "customer": "user-round",
            "service": "droplets",
            "professional": "users",
            "extra": "car-front",
        },
        "theme": {"accent": "#087e8b"},
    },
    "BARBERSHOP": {
        "name": "Barbearia",
        "labels": {
            "professional": "Barbeiro",
            "professionals": "Barbeiros",
            "appointment": "Atendimento",
            "appointments": "Agendamentos",
        },
        "dashboard": {
            "title": "Sua barbearia hoje",
            "subtitle": "Atendimentos e agenda dos barbeiros.",
            "cards": [
                {"metric": "agendamentos_hoje", "label": "Clientes hoje"},
                {"metric": "concluidos_hoje", "label": "Atendimentos concluídos"},
                {"metric": "proximos_agendamentos", "label": "Próximos horários"},
                {
                    "metric": "receita_hoje",
                    "label": "Valor estimado concluído hoje",
                    "format": "currency",
                },
                {"metric": "profissionais_ativos", "label": "Barbeiros ativos"},
            ],
        },
        "onboarding": {
            "title": "Prepare sua barbearia",
            "customer_hint": "Cadastre seus clientes.",
            "service_hint": "Cadastre cortes e outros serviços.",
        },
        "ai": {
            "guidance": (
                "Pergunte se o cliente tem barbeiro de preferência quando isso "
                "ajudar a escolher o horário."
            )
        },
        "icons": {
            "customer": "user-round",
            "service": "scissors",
            "professional": "scissors",
        },
        "theme": {"accent": "#885a36"},
    },
    "BEAUTY": {
        "name": "Beleza e estética",
        "dashboard": {
            "title": "Agenda de beleza",
            "subtitle": "Atendimentos e serviços do seu espaço.",
        },
        "ai": {
            "guidance": (
                "Confirme o serviço desejado e sua duração antes de oferecer horários."
            )
        },
        "icons": {
            "customer": "user-round",
            "service": "sparkles",
            "professional": "users",
        },
        "theme": {"accent": "#a35e7e"},
    },
    "CLINIC": {
        "name": "Clínica",
        "labels": {
            "customer": "Paciente",
            "customers": "Pacientes",
            "service": "Procedimento",
            "services": "Procedimentos",
            "professional": "Profissional",
            "professionals": "Profissionais",
            "appointment": "Consulta",
            "appointments": "Consultas",
        },
        "navigation": (
            "overview",
            "agenda",
            "appointments",
            "customers",
            "services",
            "professionals",
            "history",
            "conversations",
            "whatsapp",
            "hours",
            "business",
            "settings",
            "plan",
        ),
        "navigation_labels": {"history": "Histórico clínico"},
        "dashboard": {
            "title": "Painel da clínica",
            "subtitle": "Consultas e pacientes de hoje.",
            "cards": _CLINIC_CARDS,
        },
        "modules": ["history"],
        "onboarding": {
            "title": "Prepare sua clínica",
            "customer_hint": "Cadastre pacientes com os dados necessários.",
            "service_hint": "Cadastre procedimentos e duração.",
        },
        "ai": {
            "guidance": (
                "Use linguagem de paciente e consulta. Não faça diagnóstico; "
                "encaminhe dúvidas clínicas a um profissional."
            )
        },
        "icons": {
            "customer": "heart-pulse",
            "service": "clipboard-plus",
            "professional": "stethoscope",
        },
        "theme": {"accent": "#176c69"},
    },
    "DENTAL": {
        "name": "Odontologia",
        "labels": {
            "customer": "Paciente",
            "customers": "Pacientes",
            "service": "Procedimento",
            "services": "Procedimentos",
            "professional": "Dentista",
            "professionals": "Dentistas",
            "appointment": "Consulta",
            "appointments": "Consultas",
        },
        "navigation": (
            "overview",
            "agenda",
            "appointments",
            "customers",
            "services",
            "professionals",
            "history",
            "conversations",
            "whatsapp",
            "hours",
            "business",
            "settings",
            "plan",
        ),
        "modules": ["history"],
        "dashboard": {
            "title": "Painel odontológico",
            "subtitle": "Consultas e pacientes de hoje.",
            "cards": _CLINIC_CARDS,
        },
        "onboarding": {
            "title": "Prepare seu consultório odontológico",
            "customer_hint": "Cadastre pacientes com os dados necessários.",
            "service_hint": "Cadastre procedimentos e duração.",
        },
        "ai": {
            "guidance": (
                "Use linguagem de paciente e consulta odontológica. Não faça "
                "diagnóstico; encaminhe dúvidas clínicas ao dentista."
            )
        },
        "icons": {
            "customer": "heart-pulse",
            "service": "clipboard-plus",
            "professional": "stethoscope",
        },
    },
    "AUTO_REPAIR": {
        "name": "Oficina mecânica",
        "labels": {
            "professional": "Mecânico",
            "professionals": "Equipe",
            "appointment": "Agendamento",
            "appointments": "Ordens de serviço",
        },
        "navigation": (
            "overview",
            "agenda",
            "work_orders",
            "customers",
            "vehicles",
            "services",
            "professionals",
            "conversations",
            "whatsapp",
            "hours",
            "business",
            "settings",
            "plan",
        ),
        "dashboard": {
            "title": "Operação da oficina",
            "subtitle": "Ordens, veículos e serviços em andamento.",
            "cards": [
                {"metric": "ordens_abertas", "label": "Ordens abertas"},
                {"metric": "veiculos_em_servico", "label": "Veículos em serviço"},
                {"metric": "concluidos_hoje", "label": "Serviços concluídos"},
                {
                    "metric": "receita_estimada",
                    "label": "Receita estimada",
                    "format": "currency",
                },
                {"metric": "proximos_agendamentos", "label": "Próximos agendamentos"},
            ],
        },
        "modules": ["vehicles", "work_orders"],
        "enabled_modules": ["vehicles", "work_orders"],
        "extra_fields": {
            "customer": [],
            "appointment": [
                {"key": "vehicle_id", "label": "Veículo", "type": "entity"}
            ],
            "business": [],
        },
        "onboarding": {
            "title": "Prepare sua oficina",
            "customer_hint": "Cadastre clientes e veículos.",
            "service_hint": "Cadastre os serviços da oficina.",
        },
        "ai": {
            "guidance": (
                "Antes de agendar, liste os veículos do cliente; se não houver o "
                "correto, peça a placa e cadastre-o. Pergunte modelo, ano e "
                "problema relatado. Use o vehicle_id na reserva."
            )
        },
        "icons": {
            "customer": "user-round",
            "service": "wrench",
            "professional": "hard-hat",
            "extra": "car-front",
        },
        "theme": {"accent": "#d16a35"},
    },
    "PET": {
        "name": "Serviços pet",
        "labels": {
            "customer": "Tutor",
            "customers": "Tutores",
            "appointment": "Agendamento",
            "appointments": "Agendamentos",
        },
        "navigation": (
            "overview",
            "agenda",
            "appointments",
            "customers",
            "pets",
            "services",
            "professionals",
            "conversations",
            "whatsapp",
            "hours",
            "business",
            "settings",
            "plan",
        ),
        "dashboard": {
            "title": "Agenda pet",
            "subtitle": "Pets, tutores e atendimentos de hoje.",
            "cards": [
                {"metric": "pets_agendados_hoje", "label": "Pets agendados hoje"},
                {"metric": "em_andamento_hoje", "label": "Banhos e tosas em andamento"},
                {"metric": "concluidos_hoje", "label": "Concluídos"},
                {"metric": "proximos_agendamentos", "label": "Próximos horários"},
                {
                    "metric": "receita_hoje",
                    "label": "Valor estimado concluído hoje",
                    "format": "currency",
                },
            ],
        },
        "modules": ["pets"],
        "enabled_modules": ["pets"],
        "extra_fields": {
            "customer": [],
            "appointment": [{"key": "pet_id", "label": "Pet", "type": "entity"}],
            "business": [],
        },
        "onboarding": {
            "title": "Prepare seu negócio pet",
            "customer_hint": "Cadastre tutores e pets.",
            "service_hint": "Cadastre banho, tosa e outros serviços.",
        },
        "ai": {
            "guidance": (
                "Pergunte nome, espécie e porte do pet quando isso influenciar "
                "o serviço."
            )
        },
        "icons": {
            "customer": "user-round",
            "service": "paw-print",
            "professional": "users",
            "extra": "paw-print",
        },
        "theme": {"accent": "#a45d44"},
    },
    "HOTEL": {
        "name": "Hotel",
        "labels": {
            "customer": "Hóspede",
            "customers": "Hóspedes",
            "service": "Reserva",
            "services": "Reservas",
            "professional": "Colaborador",
            "professionals": "Equipe",
            "appointment": "Reserva",
            "appointments": "Reservas",
        },
        "navigation": (
            "overview",
            "reservations",
            "customers",
            "rooms",
            "checkins",
            "checkouts",
            "conversations",
            "whatsapp",
            "business",
            "settings",
            "plan",
        ),
        "dashboard": {
            "title": "Operação do hotel",
            "subtitle": "Reservas e ocupação em tempo real.",
            "cards": [
                {"metric": "reservas_ativas", "label": "Reservas ativas"},
                {"metric": "checkins_hoje", "label": "Check-ins hoje"},
                {"metric": "checkouts_hoje", "label": "Check-outs hoje"},
                {"metric": "quartos_ocupados", "label": "Quartos ocupados"},
                {"metric": "quartos_disponiveis", "label": "Quartos disponíveis"},
            ],
        },
        "modules": ["rooms", "reservations", "checkins", "checkouts"],
        "enabled_modules": ["rooms", "reservations", "checkins", "checkouts"],
        "extra_fields": {
            "customer": [],
            "appointment": [{"key": "room_id", "label": "Quarto", "type": "entity"}],
            "business": [],
        },
        "onboarding": {
            "title": "Prepare seu hotel",
            "customer_hint": "Cadastre hóspedes e quartos.",
            "service_hint": "Defina quartos e categorias.",
        },
        "ai": {
            "guidance": (
                "Pergunte datas de entrada e saída e quantidade de hóspedes. "
                "Só confirme reserva após verificar disponibilidade real."
            )
        },
        "icons": {
            "customer": "user-round",
            "service": "bed-double",
            "professional": "users",
            "extra": "bed-double",
        },
        "theme": {"accent": "#4d6b9c"},
    },
    "CONSULTING": {
        "name": "Consultoria",
        "labels": {
            "appointment": "Reunião",
            "appointments": "Reuniões",
            "professional": "Consultor",
            "professionals": "Consultores",
        },
        "dashboard": {
            "title": "Agenda da consultoria",
            "subtitle": "Reuniões e clientes.",
        },
        "extra_fields": {
            "customer": [{"key": "empresa", "label": "Empresa do cliente", "type": "text"}],
            "appointment": [{"key": "assunto", "label": "Assunto da reunião", "type": "text"}],
            "business": [{"key": "area_atuacao", "label": "Área de atuação", "type": "text"}],
        },
        "ai": {
            "guidance": (
                "Pergunte o tema da reunião e ofereça apenas horários disponíveis."
            )
        },
        "icons": {
            "customer": "user-round",
            "service": "briefcase-business",
            "professional": "users",
        },
    },
    "OTHER": {},
}


def _merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def get_segment_config(business_type: str | None) -> dict:
    """Return a detached, fully resolved preset; unknown legacy values use OTHER."""
    code = (business_type or "OTHER").strip().upper()
    if code not in SEGMENT_PRESETS:
        code = "OTHER"
    result = _merge(_BASE, SEGMENT_PRESETS[code])
    result["business_type"] = code
    labels = result["labels"]
    navigation_labels = result["navigation_labels"]
    dynamic = {
        "appointments": labels["appointments"],
        "customers": labels["customers"],
        "services": labels["services"],
        "professionals": labels["professionals"],
    }
    result["navigation"] = [
        {
            "id": key,
            "label": dynamic.get(key, navigation_labels.get(key, key)),
            "icon": _NAV_ICONS[key],
            "enabled": key not in _EXTRA_NAV or key in result["enabled_modules"],
        }
        for key in result["navigation"]
    ]
    return result
