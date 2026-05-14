import gradio as gr
import os
import shutil
import json
import sys

#--- 环境准备 ---
current_dir = os.path.dirname(os.path.abspath(__file__)) # 当前文件所在目录
project_root = os.path.dirname(current_dir) # 项目根目录
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from step1 import process_single_pdf
    from step2 import build_structured_dataset
    import step3
except ImportError as e:
    print(f"导入失败，请确保 step1.py、step2.py 和 step3.py 在目录 {current_dir} 中。")
    raise e

#路径配置
PDF_STORAGE_DIR = os.path.join(project_root, "Dam_Docs")
STEP1_OUTPUT = os.path.join(current_dir, "step1_outputs")
FINAL_JSON = os.path.join(current_dir, "all_docs_final.json")

os.makedirs(PDF_STORAGE_DIR, exist_ok=True)

def get_db_stats():
    """获取当前已入库的文档列表"""
    if not os.path.exists(FINAL_JSON):
        return []
    try:
        with open(FINAL_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        sources = sorted(list(set([item.get("source", "未知") for item in data])))
        return [[s] for s in sources]
    except Exception:
        return []

def search_files(query):
    """搜索功能"""
    all_sources = get_db_stats()
    if not query:
        return all_sources
    return [[s[0]] for s in all_sources if query.lower() in s[0].lower()]

def add_new_file(file_obj):
    if file_obj is None:
        return "请选择要上传的文件", get_db_stats()

    try:
        file_path = file_obj.name
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(PDF_STORAGE_DIR, file_name)
        shutil.copy(file_path, dest_path)
        
        # 第一步
        yield f"第一步：正在解析 PDF 坐标 [{file_name}]...", gr.update()
        process_single_pdf(dest_path)
        
        # 第二步
        yield "第二步：正在提取逻辑结构 (运行 step2.py)...", gr.update()
        build_structured_dataset(STEP1_OUTPUT, FINAL_JSON)
        
        # 第三步：改为分段处理或确保 ingest 完成后 yield
        yield "第三步：正在启动向量化入库 (请勿关闭页面)...", gr.update()
        
        # 执行入库
        step3.ingest() 
        
        # 关键改动：在完成任务后，先 yield 成功信息，再 yield 更新后的列表
        final_list = get_db_stats()
        yield f"✅ {file_name} 处理完成！入库成功。", final_list
        
    except Exception as e:
        yield f"❌ 出错: {str(e)}", get_db_stats()

# --- 构建 Gradio 界面 ---
with gr.Blocks(title="水利大坝数据库管理", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌊 水利大坝全生命周期专家库 - 数据库管理")
    
    with gr.Tabs():
        # 标签页 1：搜索与查看
        with gr.TabItem("🔍 库内文档搜索"):
            with gr.Row():
                search_input = gr.Textbox(label="输入文件名关键字", placeholder="例如：GB/T")
                search_btn = gr.Button("搜索", variant="primary")
            
            file_table = gr.Dataframe(
                headers=["标准名称/文件名"],
                value=get_db_stats(),
                interactive=False
            )
            
            search_btn.click(search_files, inputs=search_input, outputs=file_table)

        # 标签页 2：添加文件
        with gr.TabItem("➕ 添加新标准"):
            gr.Markdown("### 上传新的 PDF 规范文件")
            with gr.Column():
                file_input = gr.File(label="选择文件", file_types=[".pdf"])
                upload_btn = gr.Button("开始自动化入库流程", variant="primary")
                status_log = gr.Textbox(label="执行状态", interactive=False)

            upload_btn.click(
                add_new_file,
                inputs=file_input,
                outputs=[status_log, file_table]
            )

if __name__ == "__main__":
    demo.queue().launch(server_name="127.0.0.1", server_port=7861)
