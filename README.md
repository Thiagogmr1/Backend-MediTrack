# MediTrack Backend

Backend da plataforma MediTrack, um sistema de monitoramento de adesão medicamentosa com lembretes automáticos via WhatsApp.

---

# Visão Geral

O MediTrack foi desenvolvido para auxiliar médicos no acompanhamento da adesão medicamentosa de pacientes.

O sistema permite:

* Cadastro de médicos e pacientes
* Criação de prescrições médicas
* Geração automática de doses
* Lembretes automáticos via WhatsApp
* Registro automático de confirmação de doses
* Dashboard analítico de adesão
* Autenticação JWT

---

# Tecnologias Utilizadas

## Backend

* Python
* FastAPI
* PostgreSQL
* psycopg2
* APScheduler
* JWT Authentication
* passlib + bcrypt

## Integrações

* Twilio WhatsApp API

---

# Estrutura do Projeto

```bash
app/
├── auth.py
├── database.py
├── scheduler.py
├── services/
│   └── whatsapp.py
├── routes/
│   ├── auth.py
│   ├── dashboard.py
│   ├── doses.py
│   ├── patients.py
│   ├── prescriptions.py
│   └── webhook.py
```

---

# Funcionalidades

## Médicos

* Cadastro e login
* Cadastro de pacientes
* Criação de prescrições
* Cadastro de medicamentos
* Visualização de métricas de adesão
* Dashboard com dados analíticos

---

## Pacientes

* Login com CPF e data de nascimento
* Visualização das doses do dia
* Calendário de adesão
* Confirmação de medicamentos via WhatsApp

---

## Automação WhatsApp

* Envio automático de lembretes
* Scheduler executando continuamente
* Processamento automático de respostas
* Registro automático de doses tomadas

---

# Fluxo do Sistema

```text
Médico cria prescrição
        ↓
Sistema gera doses automaticamente
        ↓
Scheduler monitora horários
        ↓
WhatsApp envia lembrete
        ↓
Paciente responde “Tomei”
        ↓
Webhook recebe resposta
        ↓
Dose registrada automaticamente
        ↓
Dashboard atualizado
```

---

# Banco de Dados

## Principais tabelas

### users

Armazena médicos e pacientes.

### doctor_patients

Relacionamento entre médicos e pacientes.

### prescriptions

Prescrições médicas.

### medications

Medicamentos vinculados às prescrições.

### medication_schedules

Horários de administração dos medicamentos.

### doses

Ocorrências individuais de doses.

### dose_logs

Registro de doses confirmadas.

---

# Arquitetura das Doses

O sistema utiliza geração automática de doses utilizando:

```sql
generate_series()
```

Isso permite:

* Melhor rastreabilidade
* Métricas precisas
* Analytics simplificado
* Histórico completo de adesão

---

# Autenticação

O sistema utiliza:

* JWT
* OAuth2 Bearer Token
* bcrypt

## Controle de acesso

### Doctor

* Cadastro de pacientes
* Criação de prescrições
* Visualização de dashboards

### Patient

* Visualização de doses
* Confirmação de medicamentos

---

# Configuração do Ambiente

## 1. Clonar repositório

```bash
git clone https://github.com/Thiagogmr1/Backend-MediTrack.git
cd meditrack-backend
```

---

## 2. Criar ambiente virtual

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Instalar dependências

```bash
pip install -r requirements.txt
```

---

# Executando o Projeto

```bash
uvicorn app.main:app --reload
```

API disponível em:

```text
http://localhost:8000
```

Documentação Swagger:

```text
http://localhost:8000/docs
```

---

# Scheduler

O scheduler é iniciado automaticamente no startup da aplicação.

Funções:

* Verificar doses pendentes
* Enviar lembretes automáticos
* Evitar notificações duplicadas

---

# Webhook WhatsApp

Endpoint responsável pelo recebimento das respostas dos pacientes:

```text
POST /webhook/whatsapp
```

Exemplo de resposta esperada:

```text
Tomei
```

---

# Endpoints Principais

## Auth

```text
POST /auth/register/doctor
POST /auth/register/patient
POST /auth/login/doctor
POST /auth/login/patient
```

---

## Prescriptions

```text
POST /prescriptions
GET /prescriptions/patient/{patient_id}
```

---

## Doses

```text
GET /doses/today/{patient_id}
POST /doses/{dose_id}/take
```

---

## Dashboard

```text
GET /dashboard/overview/{doctor_id}
GET /dashboard/patient/{patient_id}
```

---

## Patients

```text
GET /patients/doctor/{doctor_id}
```

---

# Recursos Implementados

* Autenticação JWT
* Controle de acesso por perfil
* Dashboard analítico
* Scheduler automático
* Integração WhatsApp
* Webhook em tempo real
* Geração automática de doses
* Métricas de adesão

---

# Status do Projeto

MVP funcional em desenvolvimento.

---

# Licença

Projeto acadêmico.

---

# Autor

Thiago Gabriel Marques Rodrigues
Software Engineering Student

- GitHub: https://github.com/Thiagogmr1
- LinkedIn: www.linkedin.com/in/thiagogabriel10 