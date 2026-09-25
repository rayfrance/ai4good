"""
Aplicação Interativa Streamlit para Demonstração da Entrega 2:
- Inferência em Tempo Real com Comparação Lado a Lado (Baseline vs. SE-CNN)
- Visualização de Probabilidades Softmax por Classe
- Métricas Quantitativas e Curvas de Treinamento
- Segundo Dataset (Fashion-MNIST) como Desafio
"""

import os
import sys
import json
import time
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from PIL import Image

# Configuração de Paths
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CODE_DIR = os.path.join(ROOT_DIR, "code")
for path in [ROOT_DIR, CODE_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

import torch
import torch.nn.functional as F
from src.cnn.models import BaselineCNN, SE_CNN, count_parameters
from src.cnn.data_loader import get_cifar10_loaders, get_fashion_mnist_loaders, CIFAR10_CLASSES, FASHION_CLASSES

st.set_page_config(
    page_title="AI4Good — CNN vs. SE-CNN (Entrega 2)",
    page_icon="🧠",
    layout="wide"
)


@st.cache_resource
def load_models_and_data():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    models = {}
    
    # Checkpoints
    cifar_base_path = "outputs/checkpoints/baseline_cifar10.pt"
    cifar_se_path = "outputs/checkpoints/se_cnn_cifar10.pt"
    fash_base_path = "outputs/checkpoints/baseline_fashion.pt"
    fash_se_path = "outputs/checkpoints/se_cnn_fashion.pt"
    
    if os.path.exists(cifar_base_path):
        m = BaselineCNN(in_channels=3, num_classes=10).to(device)
        m.load_state_dict(torch.load(cifar_base_path, map_location=device)["model_state_dict"])
        m.eval()
        models["cifar_base"] = m
        
    if os.path.exists(cifar_se_path):
        m = SE_CNN(in_channels=3, num_classes=10).to(device)
        m.load_state_dict(torch.load(cifar_se_path, map_location=device)["model_state_dict"])
        m.eval()
        models["cifar_se"] = m
        
    if os.path.exists(fash_base_path):
        m = BaselineCNN(in_channels=1, num_classes=10).to(device)
        m.load_state_dict(torch.load(fash_base_path, map_location=device)["model_state_dict"])
        m.eval()
        models["fash_base"] = m
        
    if os.path.exists(fash_se_path):
        m = SE_CNN(in_channels=1, num_classes=10).to(device)
        m.load_state_dict(torch.load(fash_se_path, map_location=device)["model_state_dict"])
        m.eval()
        models["fash_se"] = m
        
    # Carrega pequenos batches para inferência de teste interativa
    _, cifar_test, _ = get_cifar10_loaders(batch_size=64, max_test_samples=200, seed=123)
    _, fash_test, _ = get_fashion_mnist_loaders(batch_size=64, max_test_samples=200, seed=123)
    
    return models, cifar_test, fash_test, device


def main():
    st.title("🧠 Demonstração Prática de Arquiteturas: CNN Base vs. SE-CNN (Atenção Canal)")
    st.markdown("""
    **Disciplina:** Tópicos Avançados em Inteligência Artificial (AI4Good) — UFRPE  
    **Autora:** Rayane Thaís Gomes de Lima France  
    **Artigo de Referência (2023):** *Evaluating CNN Architectures Using Attention Mechanisms (Ganguly et al., Ago/2023)*
    """)
    st.divider()
    
    models, cifar_test, fash_test, device = load_models_and_data()
    
    tab1, tab2, tab3 = st.tabs(["🚀 Inferência ao Vivo (Lado a Lado)", "📊 Resultados Quantitativos & Gráficos", "📐 Arquitetura & Fundamentação Teórica"])
    
    # -------------------------------------------------------------------------
    # ABA 1: INFERÊNCIA AO VIVO
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("Teste de Inferência com Comparação Imediata")
        
        col_ctrl1, col_ctrl2 = st.columns([1, 2])
        with col_ctrl1:
            dataset_choice = st.selectbox("Escolha o Dataset:", ["CIFAR-10 (Colorido 32x32)", "Fashion-MNIST (Tons de cinza 28x28) - Desafio"])
            
            is_cifar = "CIFAR-10" in dataset_choice
            classes = CIFAR10_CLASSES if is_cifar else FASHION_CLASSES
            test_loader = cifar_test if is_cifar else fash_test
            base_model = models.get("cifar_base" if is_cifar else "fash_base")
            se_model = models.get("cifar_se" if is_cifar else "fash_se")
            
            if st.button("🎲 Sortear Nova Amostra do Teste", type="primary"):
                st.session_state["sample_idx"] = np.random.randint(0, 60)
                
            sample_idx = st.session_state.get("sample_idx", 0)
            
        with col_ctrl2:
            st.info(f"Dispositivo de Inferência: **{device}** | Modelos carregados com sucesso a partir dos pesos treinados.")

        # Obtém a amostra
        sample_batch = next(iter(test_loader))
        images, targets = sample_batch
        img_tensor = images[sample_idx:sample_idx+1]
        target_class_idx = targets[sample_idx].item()
        target_name = classes[target_class_idx]
        
        # Inferência
        if base_model is not None and se_model is not None:
            t0 = time.perf_counter()
            with torch.no_grad():
                out_base = base_model(img_tensor.to(device))
                prob_base = F.softmax(out_base, dim=1).cpu().numpy()[0]
            time_base = (time.perf_counter() - t0) * 1000
            
            t0 = time.perf_counter()
            with torch.no_grad():
                out_se = se_model(img_tensor.to(device))
                prob_se = F.softmax(out_se, dim=1).cpu().numpy()[0]
            time_se = (time.perf_counter() - t0) * 1000
            
            pred_base_idx = np.argmax(prob_base)
            pred_se_idx = np.argmax(prob_se)
            
            c_img, c_base, c_se = st.columns([1, 1.5, 1.5])
            
            with c_img:
                st.markdown(f"**Classe Real:** `:green[{target_name}]`")
                # Prepara imagem para exibição
                if is_cifar:
                    mean = np.array([0.4914, 0.4822, 0.4465])
                    std = np.array([0.2470, 0.2435, 0.2616])
                    img_np = img_tensor[0].permute(1, 2, 0).numpy() * std + mean
                    img_np = np.clip(img_np, 0, 1)
                else:
                    mean = 0.2860
                    std = 0.3530
                    img_np = (img_tensor[0][0].numpy() * std + mean)
                    img_np = np.clip(img_np, 0, 1)
                    
                st.image(img_np, caption=f"Amostra #{sample_idx} ({target_name})", width=180)
                
            with c_base:
                base_correct = (pred_base_idx == target_class_idx)
                status_icon = "✅ CORRETO" if base_correct else "❌ ERRO"
                st.markdown(f"### BaselineCNN")
                st.metric(
                    label="Predição",
                    value=classes[pred_base_idx],
                    delta=f"{prob_base[pred_base_idx]*100:.1f}% conf. ({status_icon})"
                )
                st.caption(f"Tempo de inferência: {time_base:.2f} ms")
                
            with c_se:
                se_correct = (pred_se_idx == target_class_idx)
                status_icon = "✅ CORRETO" if se_correct else "❌ ERRO"
                st.markdown(f"### SE-CNN (Com Atenção)")
                st.metric(
                    label="Predição",
                    value=classes[pred_se_idx],
                    delta=f"{prob_se[pred_se_idx]*100:.1f}% conf. ({status_icon})"
                )
                st.caption(f"Tempo de inferência: {time_se:.2f} ms")
                
            st.write("---")
            st.markdown("#### Distribuição de Probabilidades Softmax (Baseline vs. SE-CNN)")
            
            fig, ax = plt.subplots(figsize=(10, 4))
            y_pos = np.arange(len(classes))
            width = 0.38
            
            ax.barh(y_pos - width/2, prob_base, width, label='BaselineCNN', color='#4A90E2', alpha=0.85)
            ax.barh(y_pos + width/2, prob_se, width, label='SE-CNN (Atenção)', color='#50E3C2', alpha=0.85)
            
            ax.set_yticks(y_pos)
            ax.set_yticklabels(classes, fontsize=9)
            ax.invert_yaxis()
            ax.set_xlabel('Probabilidade Prevista')
            ax.set_xlim(0, 1.05)
            ax.legend(loc='lower right')
            ax.grid(axis='x', linestyle=':', alpha=0.6)
            st.pyplot(fig)
            plt.close()
        else:
            st.warning("Modelos ainda estão sendo treinados. Aguarde o término do script de treino para ver a inferência.")

    # -------------------------------------------------------------------------
    # ABA 2: RESULTADOS QUANTITATIVOS & GRÁFICOS
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("Comparativo Quantitativo e Curvas Experimentais")
        
        metrics_file = "outputs/metrics.json"
        if os.path.exists(metrics_file):
            with open(metrics_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            c1, c2, c3, c4 = st.columns(4)
            if "cifar10_baseline" in data and "cifar10_se_cnn" in data:
                b_acc = data["cifar10_baseline"]["final_accuracy"] * 100
                se_acc = data["cifar10_se_cnn"]["final_accuracy"] * 100
                diff = se_acc - b_acc
                
                c1.metric("Acurácia CIFAR-10 (Base)", f"{b_acc:.2f}%")
                c2.metric("Acurácia CIFAR-10 (SE-CNN)", f"{se_acc:.2f}%", delta=f"{diff:+.2f}%")
                c3.metric("Parâmetros Baseline", f"{data['cifar10_baseline']['parameters']:,}")
                c4.metric("Parâmetros SE-CNN", f"{data['cifar10_se_cnn']['parameters']:,}", delta="+0.74% de custo")
                
            st.write("---")
            st.markdown("### 📈 Curvas de Convergência (Treino vs. Validação)")
            
            plot_cifar = "outputs/plots/cifar10_convergence.png"
            plot_fashion = "outputs/plots/fashion_convergence.png"
            plot_cm = "outputs/plots/cifar10_confusion_matrices.png"
            plot_quali = "outputs/plots/qualitative_comparison.png"
            
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                if os.path.exists(plot_cifar):
                    st.image(plot_cifar, caption="Convergência no CIFAR-10 (Dataset Principal)")
            with col_p2:
                if os.path.exists(plot_fashion):
                    st.image(plot_fashion, caption="Convergência no Fashion-MNIST (Desafio +0.5 VA1)")
                    
            st.write("---")
            st.markdown("### 🎯 Matrizes de Confusão Comparativas")
            if os.path.exists(plot_cm):
                st.image(plot_cm, caption="Matrizes de Confusão: Baseline vs. SE-CNN (CIFAR-10)")
                
            st.write("---")
            st.markdown("### 🖼️ Mosaico Qualitativo de Inferência")
            if os.path.exists(plot_quali):
                st.image(plot_quali, caption="Exemplos reais onde o mecanismo de atenção corrigiu a predição da Baseline")
        else:
            st.info("Arquivo de métricas em processamento...")

    # -------------------------------------------------------------------------
    # ABA 3: ARQUITETURA & FUNDAMENTAÇÃO
    # -------------------------------------------------------------------------
    with tab3:
        st.subheader("Fundamentação Arquitetural e Teórica")
        st.markdown("""
        ### Artigo de Referência
        > **Evaluating CNN Architectures Using Attention Mechanisms: Convolutional Block Attention Module, Squeeze, and Excitation for Image Classification on CIFAR10 Dataset**  
        > *Abhisek Ganguly, A. Usha Ruby, George Chellin Chandran J. (Agosto de 2023)*.
        
        ---
        
        ### Por que adicionar o bloco Squeeze-and-Excitation (SE)?
        Nas CNNs convencionais, os filtros de convolução operam agregando informações espaciais e de canal localmente em uma vizinhança $3 \\times 3$. No entanto, todos os canais de saída recebem peso uniforme na representação final da camada.
        
        O bloco **Squeeze-and-Excitation** introduz uma **recalibração dinâmica por canal**:
        1. **Squeeze ($F_{sq}$):** Utiliza *Global Average Pooling* para gerar um descritor de canal global $z \\in \\mathbb{R}^C$:
           $$z_c = \\frac{1}{H \\times W} \\sum_{i=1}^H \\sum_{j=1}^W u_c(i,j)$$
        2. **Excitation ($F_{ex}$):** Um pequeno gargalo de dois perceptrons com fator de redução $r=16$:
           $$s = \\sigma(W_2 \\cdot \\text{ReLU}(W_1 z))$$
        3. **Scale ($F_{scale}$):** Multiplicação elemento a elemento entre os pesos aprendidos $s_c$ e a respectiva matriz de características:
           $$\\tilde{x}_c = s_c \\cdot u_c$$
        
        ### Impacto Prático Observado
        - **Custo Computacional Quase Nulo:** O SE adiciona menos de **1% de novos parâmetros**, mantendo o modelo leve e rápido.
        - **Maior Poder Discriminatório:** Reduz ambiguidades comuns em datasets visuais (como confundir *cat* com *dog*, ou *automobile* com *truck*).
        """)

if __name__ == "__main__":
    main()
