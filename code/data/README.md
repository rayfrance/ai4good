# Heart Disease Dataset

**Fonte:** UCI Machine Learning Repository — Heart Disease  
**Versão usada:** Kaggle mirror com 1.025 registros (sem valores nulos)  
**URL original:** https://archive.ics.uci.edu/dataset/45/heart+disease

## Colunas

| # | Nome | Tipo | Descrição |
|---|---|---|---|
| 1 | age | int | Idade em anos |
| 2 | sex | bin | Sexo (1=masculino, 0=feminino) |
| 3 | cp | int | Tipo de dor torácica (0–3) |
| 4 | trestbps | int | Pressão arterial em repouso (mm Hg) |
| 5 | chol | int | Colesterol sérico (mg/dl) |
| 6 | fbs | bin | Glicemia em jejum > 120 mg/dl (1=sim) |
| 7 | restecg | int | Resultados do ECG em repouso (0–2) |
| 8 | thalach | int | Frequência cardíaca máxima atingida |
| 9 | exang | bin | Angina induzida por exercício (1=sim) |
| 10 | oldpeak | float | Depressão do ST induzida por exercício |
| 11 | slope | int | Inclinação do segmento ST (0–2) |
| 12 | ca | int | Vasos principais coloridos por fluoroscopia (0–3) |
| 13 | thal | int | Talassemia (0=normal, 1=defeito fixo, 2=defeito reversível) |
| 14 | target | bin | **Alvo** — presença de doença cardíaca (1=sim, 0=não) |

## Divisão usada no experimento

- **Treino:** 820 registros (80%), estratificado por `target`, semente 42
- **Teste:** 205 registros (20%), sem sobreposição com treino
- **Padronização:** µ e σ calculados exclusivamente no treino; aplicados em treino, teste e inferências

## Como baixar

```bash
# Kaggle CLI
kaggle datasets download -d johnsmith88/heart-disease-dataset
# ou coloque heart.csv nesta pasta manualmente
```

O arquivo `heart.csv` **não é versionado** (gitignored por tamanho e licença).
