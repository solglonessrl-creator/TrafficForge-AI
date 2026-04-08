# TrafficForge AI Publicidad 24/7 🚀

Sistema autónomo de generación de tráfico, captación de leads y ventas automatizadas impulsado por Inteligencia Artificial.

## 🛠 Arquitectura Modular

El sistema está dividido en módulos independientes para facilitar la escalabilidad:

- **Módulo de Tráfico (`traffic.py`)**: Genera contenido viral optimizado para TikTok, Instagram y SEO utilizando OpenAI, **Groq (Llama3)** o **Google Gemini**.
- **Módulo de Automatización (`automation.py` & `scripts/`)**: Simula comportamiento humano para navegar e interactuar en plataformas sociales usando Playwright con soporte **Multi-cuenta**.
- **Módulo de Chatbot (`chatbot.py`)**: Responde de forma inteligente a leads, clasifica su interés y utiliza scripts de venta persuasivos (OpenAI, Groq o Gemini).
- **Módulo de Embudo (`funnel.py`)**: Gestiona la captura de leads e integra **pagos automáticos con Stripe**.
- **Módulo de Email (`email_service.py`)**: Automatiza secuencias de seguimiento y bienvenida.
- **Módulo de Análisis (`analysis.py`)**: Monitoriza métricas y sugiere optimizaciones automáticas visibles en el **Dashboard integrado**.

## 🚀 Instalación y Uso

1. **Clonar el repositorio**:
   ```bash
   git clone <repo-url>
   cd TrafficForge-AI
   ```

2. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Configurar variables de entorno (`.env`)**:
   - Crea un archivo llamado `.env` en la raíz del proyecto.
   - Sigue la guía de integración abajo para obtener las llaves.

## 🔌 Guía de Integración (Plataformas)

Para que el sistema funcione, necesitas configurar las siguientes APIs:

### 1. **Supabase (Base de Datos & Auth)**
- **Qué necesitas**: `SUPABASE_URL` y `SUPABASE_KEY` (Anon Key).
- **Cómo obtenerlo**: 
  1. Ve a [Supabase.com](https://supabase.com) y crea un nuevo proyecto.
  2. En el panel lateral, ve a **Project Settings** > **API**.
  3. Copia la `Project URL` y la `anon public API Key`.
- **Uso**: El sistema usará esto para guardar leads y gestionar usuarios SaaS.

### 2. **OpenAI (IA Principal)**
- **Qué necesitas**: `OPENAI_API_KEY`.
- **Cómo obtenerlo**:
  1. Ve a [platform.openai.com](https://platform.openai.com).
  2. Ve a **API Keys** y crea una nueva (asegúrate de tener saldo en la cuenta).
- **Uso**: Generación de contenido de alta calidad y respuestas inteligentes del chatbot.

### 3. **Groq (IA Económica Llama3)**
- **Qué necesitas**: `GROQ_API_KEY`.
- **Cómo obtenerlo**:
  1. Ve a [Groq.com](https://groq.com) (o [console.groq.com](https://console.groq.com)).
  2. Crea una cuenta y obtén tu API Key (es extremadamente rápida y económica).
- **Uso**: Alternativa para reducir costes en el generador de contenido.

### 4. **Google Gemini (IA Económica/Gratis)**
- **Qué necesitas**: `GEMINI_API_KEY`.
- **Cómo obtenerlo**:
  1. Ve a [Google AI Studio](https://aistudio.google.com/).
  2. Crea una API Key (actualmente con una generosa capa gratuita).
- **Uso**: Proveedor de respaldo para generación de contenido y chat.

### 5. **Stripe (Pagos - *Opcional por ahora*)**
- **Qué necesitas**: `STRIPE_API_KEY` (Secret Key).
- **Cómo obtenerlo**:
  1. Ve a [Stripe Dashboard](https://dashboard.stripe.com).
  2. Activa el **Test Mode** (Modo Prueba).
  3. Ve a **Developers** > **API Keys** y copia la `Secret key`.
- **Uso**: Procesar suscripciones SaaS automáticamente.

---

## 🌐 Dominios de Prueba y Testing

Mientras pruebas la interfaz, puedes usar estos métodos sin comprar un dominio real:

1. **Localhost (Default)**:
   - Al ejecutar `python -m backend.app.main`, el sistema corre en `http://localhost:8000`. 
   - Ideal para desarrollo interno.

2. **Ngrok (Publicar localmente)**:
   - Si quieres ver el dashboard en tu móvil o que alguien más lo vea:
   - Instala [Ngrok](https://ngrok.com/) y ejecuta: `ngrok http 8000`.
   - Te dará una URL pública temporal (ej: `https://abcd-123.ngrok-free.app`).

3. **Render / Vercel (Gratis)**:
   - Puedes subir el código a **Render.com** (conectando tu GitHub).
   - Te darán una URL del tipo `trafficforge-ai.onrender.com` totalmente gratis y con HTTPS.

---

4. **Ejecutar el servidor**:
   ```bash
   python -m backend.app.main
   ```

## 💰 Estrategia de Monetización

1. **Venta de Servicios Directos**: Automatización de redes para clientes locales.
2. **Afiliación IA**: Promoción de herramientas SaaS de IA mediante el contenido generado.
3. **Infoproductos**: Venta del curso de marketing automatizado integrado en el chatbot.
4. **SaaS Model**: Vender el acceso a este agente como una suscripción mensual.

## 📈 Próximos Pasos (Mejoras Sugeridas)

- **SaaS Model**: Implementar sistema de suscripción multi-inquilino (multi-tenant) para revender el acceso.
- **IA de Imagen/Video**: Integración con Stable Diffusion o Sora para generar los creativos automáticamente.
- **Análisis de Sentimiento Avanzado**: Para mejorar la clasificación de leads y las respuestas del chatbot.
- **App Móvil**: Para monitorizar y lanzar campañas desde cualquier lugar.
