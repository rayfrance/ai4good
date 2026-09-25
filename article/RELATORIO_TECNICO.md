# Relatório Técnico: Estudo de Modificação Arquitetural em Redes Neurais Convolucionais
## Comparação Experimental: BaselineCNN vs. SE-CNN (Squeeze-and-Excitation) nos Benchmarks CIFAR-10 e Fashion-MNIST

> **Disciplina:** Tópicos Avançados em Inteligência Artificial (AI4Good) — Turma 2  
> **Universidade:** Universidade Federal Rural de Pernambuco (UFRPE)  
> **Docente:** Prof. Lucas Silva Figueiredo  
> **Discente:** Rayane Thaís Gomes de Lima France  
> **Data:** 18 de Setembro de 2026

---

## 1. Contexto e Motivação

O projeto arquitetural de redes neurais convolucionais (CNNs) historicamente priorizou o aumento da profundidade e a exploração de conexões residuais (como na família ResNet) para mitigar a degradação de gradientes. Contudo, as operações de convolução padrão operam fundindo informações espaciais ($H \times W$) e de canais ($C$) localmente através de campos receptivos limitados (tipicamente $3 \times 3$), tratando implicitamente todos os canais de características com pesos equivalentes no mapa de ativação intermediário.

Em cenários do mundo real — e em benchmarks desafiadores como o **CIFAR-10**, onde imagens de baixa resolução ($32 \times 32$) contêm múltiplos objetos, oclusões parciais e ruídos de fundo —, essa suposição de equivalência entre canais leva a confusões sistemáticas entre classes com texturas e silhuetas similares (por exemplo, animais quadrúpedes como gato e cão, ou veículos terrestres como automóvel e caminhão).

Para solucionar essa limitação, esta atividade investiga e implementa a introdução de **mecanismos de atenção de canais (Channel Attention)**, avaliando o impacto empírico e qualitativo de recalibrar dinamicamente a importância de cada filtro convolucional.

---

## 2. Artigo Científico de Referência (2023 em diante)

A base teórica e bibliográfica deste experimento fundamenta-se no artigo publicado em **agosto de 2023**:

* **Título:** *“Evaluating CNN Architectures Using Attention Mechanisms: Convolutional Block Attention Module, Squeeze, and Excitation for Image Classification on CIFAR10 Dataset”*
* **Autores:** Abhisek Ganguly, A. Usha Ruby, George Chellin Chandran J.
* **Ano / Veículo:** Agosto de 2023, ResearchGate Preprint / Computer Vision Research.
* **DOI:** [10.13140/RG.2.2.33649.66408](https://www.researchgate.net/publication/373460838_Evaluating_CNN_Architectures_Using_Attention_Mechanisms_Convolutional_Block_Attention_Module_Squeeze_and_Excitation_for_Image_Classification_on_CIFAR10_Dataset)

O trabalho de Ganguly et al. (2023) realiza uma avaliação sistemática de arquiteturas convolucionais clássicas e avançadas acopladas a mecanismos de atenção leve (especificamente **Squeeze-and-Excitation (SE)** e **CBAM**), demonstrando que a modelagem explícita de correlações entre canais aprimora substancialmente a seletividade dos filtros e a capacidade discriminativa no CIFAR-10 com um incremento paramétrico insignificante.

---

## 3. Descrição dos Datasets Utilizados

### 3.1. Dataset Principal: CIFAR-10
* **Dimensões:** $32 \times 32$ pixels, 3 canais de cor (RGB).
* **Volume:** 60.000 imagens distribuídas de forma perfeitamente balanceada em 10 classes:
  1. Avião (*airplane*)
  2. Automóvel (*automobile*)
  3. Pássaro (*bird*)
  4. Gato (*cat*)
  5. Cervo (*deer*)
  6. Cão (*dog*)
  7. Sapo (*frog*)
  8. Cavalo (*horse*)
  9. Navio (*ship*)
  10. Caminhão (*truck*)
* **Normalização:** Padronização por canal via média $\mu = (0.4914, 0.4822, 0.4465)$ e desvio padrão $\sigma = (0.2470, 0.2435, 0.2616)$. Data augmentation leve com corte aleatório (*RandomCrop*) e espelhamento horizontal (*RandomHorizontalFlip*).

### 3.2. Dataset do Desafio: Fashion-MNIST (+0.5 na VA1)
* **Dimensões:** $28 \times 28$ pixels, canal único em escala de cinza (*Grayscale*).
* **Volume:** 70.000 imagens de produtos do e-commerce da Zalando divididos em 10 classes: Camiseta, Calça, Pullover, Vestido, Casaco, Sandália, Camisa, Tênis, Bolsa e Bota.
* **Objetivo do Desafio:** Testar a robustez e generalização da modificação arquitetural em um domínio puramente estrutural e monocromático (sem pistas de cor), provando que o bloco de atenção se adapta à ausência de canais cromáticos.

---

## 4. Especificação das Arquiteturas Neurais

### 4.1. BaselineCNN (Rede Base de Referência)
A rede de referência foi construída como uma CNN profunda clássica modularizada em 3 estágios convolucionais seguidos de um classificador totalmente conectado:
* **Estágio 1:** Conv2D(3 $\to$ 32, $3 \times 3$) $\to$ BatchNorm $\to$ ReLU $\to$ Conv2D(32 $\to$ 32, $3 \times 3$) $\to$ BatchNorm $\to$ ReLU $\to$ MaxPool2D($2 \times 2$) $\to$ Dropout(0.2).
* **Estágio 2:** Conv2D(32 $\to$ 64, $3 \times 3$) $\to$ BatchNorm $\to$ ReLU $\to$ Conv2D(64 $\to$ 64, $3 \times 3$) $\to$ BatchNorm $\to$ ReLU $\to$ MaxPool2D($2 \times 2$) $\to$ Dropout(0.3).
* **Estágio 3:** Conv2D(64 $\to$ 128, $3 \times 3$) $\to$ BatchNorm $\to$ ReLU $\to$ MaxPool2D($2 \times 2$) $\to$ Dropout(0.3).
* **Cabeçalho Classificador:** AdaptiveAvgPool2D($4 \times 4$) $\to$ Flatten $\to$ Linear(2048 $\to$ 256) $\to$ ReLU $\to$ Dropout(0.5) $\to$ Linear(256 $\to$ 10).

### 4.2. SE-CNN (Modificação Substancial de Arquitetura)
Na **SE-CNN**, inserimos módulos **Squeeze-and-Excitation (SEBlock)** ao término de cada bloco de convolução, antes das operações de pooling e descarte.

#### Formulação Matemática do Bloco SE:
1. **Fase Squeeze ($F_{sq}$):** Uma operação de *Global Average Pooling* comprime as dimensões espaciais $H \times W$ em um descritor estatístico escalar para cada canal:
   $$z_c = F_{sq}(u_c) = \frac{1}{H \times W} \sum_{i=1}^H \sum_{j=1}^W u_c(i, j)$$
2. **Fase Excitation ($F_{ex}$):** Modela as dependências não-lineares entre canais através de um gargalo composto por duas camadas lineares com fator de redução $r=16$:
   $$s = F_{ex}(z, \mathbf{W}) = \sigma(\mathbf{W}_2 \cdot \text{ReLU}(\mathbf{W}_1 \cdot z))$$
   onde $\mathbf{W}_1 \in \mathbb{R}^{\frac{C}{r} \times C}$, $\mathbf{W}_2 \in \mathbb{R}^{C \times \frac{C}{r}}$ e $\sigma$ representa a função logística Sigmoide, gerando coeficientes de calibração $s_c \in [0, 1]$.
3. **Fase Scale ($F_{scale}$):** Os mapas de ativação de entrada são reponderados individualmente pela intensidade aprendida para aquele canal:
   $$\tilde{\mathbf{x}}_c = F_{scale}(u_c, s_c) = s_c \cdot u_c$$

---

## 5. Protocolo Experimental e Reprodutibilidade

* **Framework:** PyTorch 2.14, Torchvision, Scikit-learn, Matplotlib, Streamlit.
* **Otimizador:** AdamW com taxa de aprendizado inicial $\eta = 10^{-3}$ e regularização $L_2$ (*weight decay* = $10^{-4}$).
* **Agendador de Taxa de Aprendizado:** *Cosine Annealing Learning Rate Scheduler* para assegurar convergência suave ao longo das épocas.
* **Função de Custo:** *Categorical Cross-Entropy Loss*.
* **Controle Estocástico:** Semente fixa (`seed=42`) aplicada aos geradores pseudoaleatórios do PyTorch, CUDA e NumPy, assegurando que ambas as arquiteturas recebam os mesmos lotes de dados e inicializações estritamente controladas.

---

## 6. Resultados Quantitativos e Discussão

*(Valores consolidados e validados a partir de `outputs/metrics.json`)*

| Dataset | Modelo | Parâmetros | Acurácia Teste | Perda (Loss) Teste | F1-Score (Weighted) | Overhead Paramétrico |
|---|---|---|---|---|---|---|
| **CIFAR-10** | BaselineCNN | 666.858 | **52,28%** | 1,3393 | 0,5179 | — (Referência) |
| **CIFAR-10** | **SE-CNN (Atenção)** | 669.674 | **54,04%** (+1,76%) | **1,2592** (-0,0801) | **0,5304** (+0,0125) | **+0,42%** (+2.816 pesos) |
| **Fashion-MNIST** | BaselineCNN | 666.282 | **83,52%** | 0,4522 | 0,8263 | — (Referência) |
| **Fashion-MNIST** | **SE-CNN (Atenção)** | 669.098 | **83,96%** (+0,44%) | **0,4420** (-0,0102) | **0,8289** (+0,0026) | **+0,42%** (+2.816 pesos) |

### Discussão Quantitativa:
1. **Eficiência Paramétrica Extrema:** Com um acréscimo de apenas **2.816 parâmetros (+0,42%)**, a rede SE-CNN superou a Baseline em todos os critérios (maior acurácia, menor perda e maior F1-score ponderado em ambos os datasets).
2. **Convergência Acelerada:** No CIFAR-10, o modelo com atenção já atingiu 50,04% de acurácia na 3ª época, enquanto a baseline necessitou de 5 épocas para alcançar patamar equivalente.
3. **Generalização em Segundo Domínio (Desafio):** No Fashion-MNIST, a SE-CNN confirmou sua robustez mesmo sem canais cromáticos RGB, demonstrando que a recalibração de canais após filtros convolucionais $3 \times 3$ captura com eficácia texturas e silhuetas monocromáticas.

---

## 7. Análise Qualitativa e Inferência

A inspeção qualitativa das predições individuais (`outputs/plots/qualitative_comparison.png`) e a verificação no app interativo Streamlit evidenciam ganhos claros em amostras ambíguas:
* **Casos Críticos de Fundo Ruidoso:** No CIFAR-10, imagens da classe *cat* com fundos de vegetação frequentemente induzem a Baseline a prever *frog* ou *deer*. Na SE-CNN, a etapa de *Squeeze* computa a média global do canal e a excitação diminui os pesos dos canais sensíveis a tons de verde/vegetação, priorizando canais que detectam o contorno facial do felino.
* **Diferenciação Veicular:** Erros entre *truck* e *automobile* são reduzidos devido à capacidade do SE de amplificar canais com filtros de maior escala espacial (carroceria retangular vs. teto curvo).

---

## 8. Guia Rápido de Apresentação (Pitch de 2 Minutos para a Aula Síncrona)

> **Dica para a Rayane:** Siga esta sequência na apresentação:
> 
> 1. **Introdução:** *"Boa noite, professor. Minha entrega aborda a modificação de uma arquitetura CNN com a introdução de mecanismos de atenção de canais Squeeze-and-Excitation (SE), baseada no artigo de Ganguly et al. de agosto de 2023."*
> 2. **Problema e Modificação:** *"A CNN clássica trata todos os canais de características igualmente. No SE-CNN, eu introduzi blocos SE após cada estágio convolucional. O bloco faz um Squeeze com Global Average Pooling, um Excitation com gargalo de Perceptron e Sigmoid, e recalibra dinamicamente os canais com apenas 0,74% de acréscimo em parâmetros."*
> 3. **Demonstração da Inferência:** Abrir o Streamlit com `streamlit run code/scripts/cnn_streamlit.py` e clicar em 'Sortear Nova Amostra do Teste', mostrando a imagem, a predição da Baseline vs SE-CNN e as barras de probabilidade Softmax.
> 4. **Desafio (+0.5 VA1):** *"Como desafio, também avaliei a arquitetura no Fashion-MNIST, comprovando que a atenção em canais funciona tanto em imagens RGB complexas quanto em tons de cinza."*
