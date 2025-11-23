from graph.builder import build_graph
import os


def visualize_pipeline():
    """
    AI 에이전트 파이프라인을 빌드하고 Mermaid 다이어그램으로 시각화하여 PNG 파일로 저장합니다.
    """
    print("AI 에이전트 파이프라인 빌드를 시작합니다...")
    
    # main.py와 동일하게 그래프(Agent)를 빌드합니다.
    app = build_graph()
    
    print("파이프라인 그래프를 생성 중입니다...")
    
    try:
        # get_graph()를 통해 그래프 객체를 가져오고, draw_mermaid_png()로 시각화합니다.
        # 이 메서드는 PNG 이미지 데이터를 바이트 형태로 반환합니다.
        png_bytes = app.get_graph().draw_mermaid_png()
        
        # 생성된 이미지 데이터를 파일로 저장합니다.
        output_filename = "results/pipeline_visualization.png"
        with open(output_filename, "wb") as f:
            f.write(png_bytes)
            
        print(f"성공적으로 파이프라인 시각화 이미지를 '{os.path.abspath(output_filename)}'에 저장했습니다.")

    except Exception as e:
        print(f"시각화 중 오류가 발생했습니다: {e}")
        print("graphviz 또는 관련 라이브러리가 설치되었는지 확인해주세요.")


if __name__ == "__main__":
    visualize_pipeline()
