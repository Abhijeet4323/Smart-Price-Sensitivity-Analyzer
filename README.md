# ⚡ Price Sensitivity Intelligence (PSI) Engine

> **Bridging the gap between Causal Inference and Machine Learning.**

**Developed by:** Anany Tripathi  
**Profile:** B.Tech in AI & ML (AKS University) | BS in Data Science & Applications (IIT Madras)  

---

## 🔬 Theoretical Grounding

At the core of the Price Sensitivity Intelligence (PSI) Engine lies rigorous econometrics. To calculate Price Elasticity of Demand (PED), the system employs Log-Log Regression via Ordinary Least Squares (OLS). 

The governing econometric equations are defined as:

$$ \ln(Q) = \beta_0 + \beta_1 \ln(P) + \epsilon $$

**Why the Log-Log Transform?**
Applying a logarithmic transformation to both the dependent variable (Quantity, $Q$) and the independent variable (Price, $P$) logically enforces a *constant elasticity model*. In this framing, the coefficient $\beta_1$ represents the strict, isolated price elasticity—the percentage change in demand given a 1% change in price. This explicitly isolates the causal effect, enabling systemic classification of demand behavior as **Elastic** ($|\beta_1| > 1$) or **Inelastic** ($|\beta_1| < 1$).

## 🏛️ The Architecture

The system operates on an advanced **Multi-Model Approach** to maintain theoretical purity and capture category-specific nuances without introducing confounding biases across disparate product lines.

- **Independent XGBoost Instantiation:** Rather than deploying a monolithic global predictor, a discrete XGBoost instance is dynamically trained per individual product category. This localized architecture captures non-linear relationships and nuanced seasonal/lag features uniquely tied to specific retail verticals.
- **Enterprise Tech Stack:** The robust data layer heavily utilizes **Python 3.12+**, **Flask** for the API/Backend conduit, **XGBoost** for extreme gradient boosted non-linear demand modeling, **Pandas** for tensor and tabular processing, and **Plotly.js** for rendering interactive, enterprise-grade causality visuals.

## 🚀 Key Features

This analytical interface transcends traditional descriptive reporting; it is structurally designated as a **Prescriptive AI**. It does not merely reflect elasticities—it computationally bounds and dictates maximal revenue states.

*   **Scenario Simulator (₹):** Dynamically inject speculative price vectors into the inference engine to observe deterministic and highly-correlated impacts on projected demand.
*   **Revenue Potential Path (OPTM Line):** Employs a continuous 3rd-order polynomial smoothing technique mathematically layered over discrete XGBoost predictions to derive a statistically sound, unified revenue curve.
*   **AI-Powered Prescriptive Advice:** Auto-computes the absolute 'Optimal Price Point'—the mathematical relative maximum of the continuous revenue curve—prescribing the exact empirical pricing strategy required to capture maximal commercial yield.

## 🗺️ Technical Roadmap

The execution pipeline for the PSI Engine successfully ingested, strictly standardized, and modeled **294,447+ rows** sourced from the Olist Brazilian E-commerce and standard Retail datasets.

*   **Data Cleaning:** Aggressive curation and normalization protocols, systematically targeting edge-case anomalies and directly handling ambiguous `Object`-dtype permutations to guarantee high-fidelity tensor inputs.
*   **Feature Engineering:** Deliberate implementation of temporal causal features, prominently including *Lagged Prices*, shifting the model state to respect historically observed pricing inertia and user anchor pricing.
*   **Polynomial Smoothing:** Functional mitigation of decision-tree step-function extrapolation artifacts via high-order polynomial regression techniques. This ensures fully differentiable and structurally smooth revenue optimization geometries.

## 💻 Installation & Usage

To initialize and deploy the quantitative intelligence engine natively:

```bash
# 1. Clone the repository and navigate to the project root
git clone <repository_url>
cd Price-Sensitivity-Analyzer

# 2. Establish a sterile Python 3.12+ virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows executing: venv\Scripts\activate

# 3. Install strict mathematical and backend dependencies
pip install -r requirements.txt

# 4. Trigger the synthetic causality data generation pipeline
python generate_data.py

# 5. Ignite the Flask Application Server
python app.py
```

*The application protocol will bind to `http://127.0.0.1:5000`. Access via any modern browser client to initialize the analytical dashboard and visually query the optimization model.*
