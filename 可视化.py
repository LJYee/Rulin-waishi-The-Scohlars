import pandas as pd
import numpy as np
import folium
import streamlit as st
from streamlit_folium import st_folium #anaconda environment里apply
from pyvis.network import Network
import streamlit.components.v1 as components

# 读取数据
#df = pd.read_csv("/Users/ye/CHC 5904/my_streamlit_app/读取1.csv", encoding='utf-8')
df = pd.read_csv("读取1.csv", encoding='utf-8') #在github里 streamlit里
#改名字用于调用
df.rename(columns={
    '回次': 'chapter',
    '地名': 'location',
    '经度': 'lon',
    '纬度': 'lat',
    '城市出现次数': 'loc_total_freq',  # 地点总出现次数
    '涉及主要人物': 'characters',
    '活动类型': 'activity_type',
    '情节': 'plot_summary'
}, inplace=True)

# 做关联图，生成节点唯一ID（
# 1. 地点ID
locations = df['location'].unique()
loc_id_map = {loc: f'loc_{str(i+1).zfill(3)}' for i, loc in enumerate(locations)}
df['location_id'] = df['location'].map(loc_id_map)

# 2. 人物ID（拆分多人物）
all_chars = []
for chars in df['characters']:
    all_chars.extend([c.strip() for c in chars.split('，')])
all_chars = list(set(all_chars))  # 去重
char_id_map = {char: f'char_{str(i+1).zfill(3)}' for i, char in enumerate(all_chars)}

# 3. 活动类型ID
activities = df['activity_type'].unique()
act_id_map = {act: f'act_{str(i+1).zfill(3)}' for i, act in enumerate(activities)}
df['activity_type_id'] = df['activity_type'].map(act_id_map)

# 统计地点的章回分布（每个地点出现在哪些章回、每章出现次数）
loc_chapter_stats = df.groupby('location').agg({
    'chapter': lambda x: list(set(x)),  # 出现在的章回（去重）
    'loc_total_freq': 'first'  # 地点总出现次数
}).reset_index()
loc_chapter_stats['chapter_count'] = loc_chapter_stats['chapter'].apply(len)  # 出现在的章回数
# 统计每章出现次数（如：京师在第10回出现2次）
loc_chapter_detail = df.groupby(['location', 'chapter']).size().reset_index(name='chapter_freq')
loc_chapter_detail['chapter_freq_str'] = loc_chapter_detail.apply(
    lambda x: f"第{x['chapter']}回：{x['chapter_freq']}次", axis=1
)
loc_chapter_detail = loc_chapter_detail.groupby('location')['chapter_freq_str'].apply(list).reset_index()
# 合并统计结果
loc_stats = loc_chapter_stats.merge(loc_chapter_detail, on='location')
# 标题
def fix_title_to_top():
    with st.container():
        st.markdown('<div class="fixed-header">', unsafe_allow_html=True)
        st.title('《儒林外史》可视化分析')
        st.markdown('以《儒林外史》第10-29章回为材料进行可视化分析地点与人物活动之间的关联，探究不同地点的人物活动特征')
        st.markdown('</div>', unsafe_allow_html=True)
fix_title_to_top()
#页面，设计三个页面显示地图、关联图、表格
tab1, tab2, tab3 = st.tabs([
    "1. 地点坐标地图", 
    "2. 双维度关联网络图", 
    "3. 地点-人物-活动统计表"
])
#tab1-地点坐标地图
with tab1:
    st.title("《儒林外史》地点坐标地图")
    st.caption("侧边栏滑动筛选章回可查看不同章回地点地图")
    st.sidebar.header("地图筛选条件") #侧边栏
    #1.地点筛选（用rename后的location字段）
    selected_locs = st.sidebar.multiselect(
        "选择地点", 
        df['location'].unique(), 
        default=df['location'].unique(),  # 默认全选
        key="tab1_location"   
    )
    #2.活动类型筛选（用rename后的activity_type字段）
    selected_acts = st.sidebar.multiselect(
        "选择活动类型", 
        df['activity_type'].unique(), 
        default=df['activity_type'].unique(),
        key="tab1_activity" 
    )
    #3.章回范围筛选（用rename后的chapter字段，确保整数类型）
    min_chapter = int(df['chapter'].min())
    max_chapter = int(df['chapter'].max())
    selected_chapters = st.sidebar.slider(
        "选择章回范围", 
        min_value=min_chapter, 
        max_value=max_chapter, 
        value=(min_chapter, max_chapter)
    )
    # 应用筛选条件（基于rename后的字段）
    filtered_df = df[
        (df['location'].isin(selected_locs)) &
        (df['activity_type'].isin(selected_acts)) &
        (df['chapter'] >= selected_chapters[0]) &
        (df['chapter'] <= selected_chapters[1])
    ]
    if filtered_df.empty:
        st.warning("暂无符合条件的数据，请调整筛选条件！")
    else:
        # 1. 创建地图-调整经纬度和大小 更方便直接显示相关地点
        m = folium.Map(location=[36.0000, 117.0000], zoom_start=5, tiles="CartoDB positron")
        # 2. 为每个地点添加标记（核心：用rename后的loc_total_freq字段统计）
        for loc in filtered_df['location'].unique():
            # 提取当前地点的筛选数据（含多活动标签行）
            loc_filtered_data = filtered_df[filtered_df['location'] == loc]
            loc_base_data = loc_filtered_data.iloc[0]  # 取1行获取经纬度/情节等基础信息
            # 统计（基于loc_total_freq）
            #1.总出现次数：按“地点+章回”去重后，求和loc_total_freq
            #同一地点同一章回只保留1行（同一章回同一地点不同活动分不同行，防止重复统计次数）
            loc_chapter_unique = loc_filtered_data[['chapter', 'loc_total_freq']].drop_duplicates()
            total_freq = int(loc_chapter_unique['loc_total_freq'].sum())  # 求和得到总出现次数
            #2.每章出现次数：读取去重后的loc_total_freq
            chapter_freq_dict = dict(zip(loc_chapter_unique['chapter'], loc_chapter_unique['loc_total_freq']))
            chapter_freq_str = [f"第{int(chap)}回：{int(freq)}次" for chap, freq in chapter_freq_dict.items()]
            #3.涉及章回统计-去除重复统计版
            chapter_list = sorted(loc_chapter_unique['chapter'].tolist())  # 排序章回
            chapter_count = len(chapter_list)  # 涉及章回数
            #活动类型统计
            act_freq_dict = loc_filtered_data['activity_type'].value_counts().to_dict()
            act_freq_str = "\n".join([f"{act}：{int(freq)}次" for act, freq in act_freq_dict.items()])
            main_act = max(act_freq_dict, key=act_freq_dict.get) if act_freq_dict else "其他"
            
            # 活动类型颜色映射
            act_color_map = {
                 "官场任职": "#E67E22",  
                 "家庭生活": "#EEAA9C",  
                 "科举备考": "#3498DB",  
                 "商业经济": "#8E44AD",  
                 "社交往来": "#F39C12",  
                 "特殊变故": "#E74C3C",  
                 "文人雅集": "#b9dec9",  
                 "其他": "#95A5A6"     
            }
            marker_color = act_color_map.get(main_act, act_color_map["其他"])
            # 先计算筛选后所有地点的最大总次数 大小按比例
            max_total_freq = max([
                int(filtered_df[filtered_df['location'] == temp_loc][['chapter', 'loc_total_freq']].drop_duplicates()['loc_total_freq'].sum())
                for temp_loc in filtered_df['location'].unique()
            ])
            marker_radius = 12 + (total_freq / max_total_freq) * 20
            #处理空值（避免情节为NaN报错）
            plot_content = loc_base_data['plot_summary'][:120] if pd.notna(loc_base_data['plot_summary']) else "无相关情节"
            #添加地图标记（hover+弹窗）
            folium.CircleMarker(
                location=[loc_base_data['lat'], loc_base_data['lon']],  # folium要求：纬度在前，经度在后
                radius=marker_radius,
                color=marker_color,
                fill=True,
                fill_color=marker_color,
                fill_opacity=0.8,
                # Hover提示：核心信息快速预览
                tooltip=f"""
                    <b>{loc}</b><br>
                    总出现次数：{total_freq}次<br>
                    涉及章回：{chapter_count}回<br>
                    主要活动：{main_act}
                """,
                # 点击弹窗：详细信息（含人物、情节）
                popup=folium.Popup(f"""
                    <div style='width:280px; font-size:14px; line-height:1.5'>
                        <h4 style='margin:0; color:{marker_color}; font-size:16px'>{loc}</h4>
                        <p><b>1. 出现统计</b></p>
                        <p>总出现次数：{total_freq}次</p>
                        <p>涉及章回：{chapter_count}回（{', '.join(map(str, map(int, chapter_list)))}）</p>
                        <p>每章出现次数：<br>{'<br>'.join(chapter_freq_str)}</p>
                        <p><b>2. 核心信息</b></p>
                        <p>涉及主要人物：{loc_base_data['characters'] if pd.notna(loc_base_data['characters']) else "无"}</p>
                        <p>主要活动类型：{main_act}</p>
                        <p><b>3. 情节示例</b></p>
                        <p>{plot_content}...</p>
                    </div>
                """, max_width=300)
            ).add_to(m)
        # 3. 渲染地图（占满页面宽度，高度700px适配屏幕）
        st_folium(m, width="100%", height=700)
        st.caption("悬浮可见小视窗，了解该城市总出现次数，涉及章回数目，主要活动类型")
        st.caption("点击地点可查看详细信息,了解具体章回，主要人物，情节示例")
        # 4. 筛选结果统计表格（基于loc_total_freq字段，与地图逻辑一致）
        st.subheader("筛选结果统计（地点维度）")
        result_stats = []
        for loc in filtered_df['location'].unique():
            loc_data = filtered_df[filtered_df['location'] == loc]
            # 按“章回+loc_total_freq”去重后统计
            loc_chapter_unique = loc_data[['chapter', 'loc_total_freq']].drop_duplicates()
            total_freq = int(loc_chapter_unique['loc_total_freq'].sum())
            chapter_list = sorted(loc_chapter_unique['chapter'].tolist())
            chapter_str = f"{len(chapter_list)}回（{', '.join(map(str, map(int, chapter_list)))}）"
            # 活动类型统计
            act_freq = loc_data['activity_type'].value_counts().to_dict()
            act_str = "\n".join([f"{act}：{int(freq)}次" for act, freq in act_freq.items()])
            # 主要人物
            main_char = loc_data['characters'].value_counts().index[0] if len(loc_data['characters'].dropna()) > 0 else "无"
            result_stats.append({
                '序号': len(result_stats) + 1,
                '地点': loc,
                '总出现次数': total_freq,
                '涉及章回': chapter_str,
                '主要涉及人物': main_char,
                '活动类型统计': act_str
            })
        # 显示表格（序号设为索引，提升可读性）
        result_df = pd.DataFrame(result_stats)
        st.dataframe(result_df.set_index('序号'), height=400)

# tab2-关联网络图，人物-地点，活动-地点
with tab2:
    st.title("《儒林外史》双维度关联网络图")
    st.caption("侧边栏滑动筛选章回可查看不同章回关联内容")
    st.markdown("### 一、人物-地点关联图谱")
    st.sidebar.header("网络图筛选条件")  # 侧边栏筛选：控制网络图数据范围
    # 1. 地点筛选（支持多选，默认全选）
    selected_locs_net = st.sidebar.multiselect(
        "选择关联地点（默认全选）",
        df['location'].unique(),
        default=df['location'].unique(),
        key="net_location_filter"
    )
    # 2. 人物筛选（支持多选，默认全选，处理空值）
    all_chars = list(set([
        c.strip() for chars in df['characters'].dropna() 
        for c in chars.split('，') if c.strip()
    ]))
    selected_chars_net = st.sidebar.multiselect(
        "选择关联人物（默认全选）",
        sorted(all_chars),  # 按字母排序，便于选择
        default=sorted(all_chars),
        key="net_char_filter"
    )
    # 3. 章回范围筛选（控制数据时间范围）
    selected_chapters_net = st.sidebar.slider(
        "选择章回范围",
        min_value=int(df['chapter'].min()),
        max_value=int(df['chapter'].max()),
        value=(int(df['chapter'].min()), int(df['chapter'].max())),
        key="net_chapter_slider"
    )
    # 第一步：筛选数据（按章回、地点、人物）
    net_df = df[
        (df['chapter'] >= selected_chapters_net[0]) &
        (df['chapter'] <= selected_chapters_net[1]) &
        (df['location'].isin(selected_locs_net))
    ].copy()
    # 处理人物数据：拆分多人物，仅保留选中的人物
    def filter_chars(char_str):
        """拆分人物字符串，保留选中的人物"""
        if pd.isna(char_str):
            return []
        return [c.strip() for c in char_str.split('，') if c.strip() in selected_chars_net]
    net_df['filtered_chars'] = net_df['characters'].apply(filter_chars)
    # 过滤掉无选中人物的行
    net_df = net_df[net_df['filtered_chars'].apply(len) > 0].reset_index(drop=True)
    
    if net_df.empty:
        st.warning("暂无符合条件的人物-地点关联数据，请调整筛选条件！")
    else:
        # 第二步：统计节点频次（用于动态调整节点大小）
        # 1. 地点频次：按loc_total_freq求和（总出现次数）
        net_df_unique = net_df.drop_duplicates(
            subset=['chapter', 'location'],  # 关键：按“章回+地点”去重，替换“chapter”为你的章回列名（如“章回”）
            keep='first'  # 保留每组第一行数据（同一章回+地点的行，loc_total_freq相同，保留哪行都一样）
            )
        loc_freq = net_df_unique.groupby('location')['loc_total_freq'].sum().reset_index()
        loc_freq.columns = ['node', 'freq']
        loc_freq['type'] = '地点'  # 标记节点类型
        # 2. 人物频次：统计人物在筛选数据中的出现次数
        char_freq_list = []
        for _, row in net_df.iterrows():
            for char in row['filtered_chars']:
                char_freq_list.append({'char': char, 'loc': row['location']})
        char_freq_df = pd.DataFrame(char_freq_list)
        char_freq = char_freq_df['char'].value_counts().reset_index()
        char_freq.columns = ['node', 'freq']
        char_freq['type'] = '人物'  # 标记节点类型
        # 合并节点频次，统一处理
        node_freq = pd.concat([loc_freq, char_freq], ignore_index=True)
        # 节点大小映射：频次→大小
        min_size = 20
        max_size = 80
        node_freq['size'] = node_freq['freq'].apply(
            lambda x: min_size + (max_size - min_size) * (x - node_freq['freq'].min()) / 
            (node_freq['freq'].max() - node_freq['freq'].min()) if node_freq['freq'].max() > node_freq['freq'].min() else 30
        )
    
        # 第三步：构建人物-地点双节点网络
        from pyvis.network import Network
        # 初始化网络图（设置尺寸、背景色，关闭notebook模式）
        net = Network(
            directed=False,  # 无向图，双向关联）
            notebook=False,
            height="800px",  # 高
            width="100%",    # 宽
            bgcolor="#f8f9fa", 
            font_color="#333333" 
        )
        # 1. 添加节点（先添加地点，再添加人物，避免重叠）
        # 地点节点，标签显示“地点（频次）”
        for _, row in loc_freq.iterrows():
            loc = row['node']
            freq = row['freq']
            size = node_freq[node_freq['node'] == loc]['size'].iloc[0]
            # Hover提示：显示地点关联的所有人物
            related_chars = char_freq_df[char_freq_df['loc'] == loc]['char'].unique()
            title = f"地点：{loc}\n总出现次数：{freq}次\n关联人物：{', '.join(related_chars) if len(related_chars) > 0 else '无'}"
            net.add_node(
                n_id=f"loc_{loc}",  # 节点ID前缀：loc_，避免与人物ID冲突
                label=f"{loc}\n（{freq}次）",  # 标签：地点+频次
                size=size,
                color="#5D2B09",  # 区分地点节点
                title=title,  # Hover提示
                font={"size": 12, "weight": "bold"}  # 字体加粗，提升辨识度
            )
        # 人物节点：标签显示“人物（频次）”
        for _, row in char_freq.iterrows():
            char = row['node']
            freq = row['freq']
            size = node_freq[node_freq['node'] == char]['size'].iloc[0]
            # Hover提示：显示人物关联的所有地点
            related_locs = char_freq_df[char_freq_df['char'] == char]['loc'].unique()
            title = f"人物：{char}\n关联地点数：{freq}个\n关联地点：{', '.join(related_locs) if len(related_locs) > 0 else '无'}"
            net.add_node(
                n_id=f"char_{char}",  # 节点ID前缀：char_，避免与地点ID冲突
                label=f"{char}\n（{freq}个地点）",  # 标签：人物+关联地点数
                size=size,
                color="#DAC6B2",  # 区分人物节点
                title=title,  # Hover提示
                font={"size": 12, "weight": "bold"}
            )
        # 2. 添加边（人物-地点关联，仅添加一次，避免重复）
        edge_set = set()  # 用集合去重，避免同一人物-地点添加多条边
        for _, row in net_df.iterrows():
            loc = row['location']
            loc_node_id = f"loc_{loc}"
            for char in row['filtered_chars']:
                char_node_id = f"char_{char}"
                edge_key = tuple(sorted([char_node_id, loc_node_id]))
                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    # 边的hover提示：显示关联的章回和活动类型
                    chapters = sorted(net_df[(net_df['location'] == loc) & (net_df['filtered_chars'].apply(lambda x: char in x))]['chapter'].unique())
                    acts = net_df[(net_df['location'] == loc) & (net_df['filtered_chars'].apply(lambda x: char in x))]['activity_type'].unique()
                    edge_title = f"关联：{char} ↔ {loc}\n涉及章回：{', '.join(map(str, chapters))}\n参与活动：{', '.join(acts)}"
                    net.add_edge(
                        char_node_id,
                        loc_node_id,
                        color="#9AA0A6",  # 灰色边：不抢节点视觉焦点
                        width=2,  # 边宽度：适中，便于识别
                        title=edge_title,  # Hover提示：显示关联细节
                        smooth=True  # 平滑边：提升图谱美观度
                    )
        
        # 第四步：优化图谱布局与交互
        # 1. 设置物理引擎参数（避免节点过度重叠）
        net.barnes_hut(
            gravity=-3000,  # 引力：负值，让节点分散
            central_gravity=0.3,  # 中心引力：适中，避免节点偏离中心
            spring_length=200,  # 弹簧长度：控制节点间距
            spring_strength=0.05,  # 弹簧强度：避免节点过近
            damping=0.4  # 阻尼：控制节点运动速度，避免震荡
        )
        # 2. 显示关键调节按钮（仅保留物理参数、节点、边，避免冗余）
        net.show_buttons(["physics", "nodes", "edges"])
        # 3. 保存图谱到本地-适配macOS路径，避免/mnt问题）
        # 替换保存和显示逻辑：用Streamlit临时目录+components.v1.html加载
        import streamlit.components.v1 as components
        import os
        import tempfile
        # 保存图谱到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
           net.save_graph(f.name)
           temp_path = f.name
        #import os
        #net_save_path = "/Users/ye/Desktop/人物地点双节点网络图.html"
        #net.save_graph(net_save_path)
        # 4. 在Streamlit中显示图谱【用iframe嵌入，支持交互
        st.subheader("人物-地点关联图谱")
        with open(temp_path, "r", encoding="utf-8") as f:
             html_content = f.read()
             components.html(html_content, width="100%", height=800, scrolling=True)
        st.caption("深色=地点（大小=总出现次数）" \
                   "浅色=人物角色" 
        )

    st.markdown("### 二、地点-活动类型关联图谱")  
    # 1. 地点-活动关联图谱
    selected_acts_net = st.sidebar.multiselect(
        "选择关联活动类型（默认全选）",
        df['activity_type'].unique(),
        default=df['activity_type'].unique(),
        key="net_act_filter"
    )
    # 应用筛选（地点、章回、活动类型）
    net_df_loc_act = df[
        (df['chapter'] >= selected_chapters_net[0]) &
        (df['chapter'] <= selected_chapters_net[1]) &
        (df['location'].isin(selected_locs_net)) &
        (df['activity_type'].isin(selected_acts_net))
    ].copy()
    
    net_df_loc_act_unique = net_df_loc_act.drop_duplicates(
    subset=['chapter', 'location'],  # 按“章回+地点”去重，核心去重条件
    keep='first'  # 保留每组第一行（同一章回+地点的loc_total_freq相同
    )
    # 2. 地点-活动图谱：生成与显示
    if net_df_loc_act_unique.empty:
        st.warning("暂无符合条件的地点-活动关联数据，请调整筛选条件！")
    else:
        # 初始化地点-活动网络图
        net_loc_act = Network(
            directed=False, height="600px", width="100%",
            bgcolor="#f8f9fa", font_color="#333333"
        )
        #1.添加地点节点（大小=总出现次数）
        loc_stats_act = net_df_loc_act_unique.groupby('location').agg({
            'loc_total_freq': 'sum',
            'activity_type': lambda x: x.value_counts().to_dict()
        }).reset_index()
        for _, row in loc_stats_act.iterrows():
            loc = row['node'] if 'node' in row else row['location']  # 兼容字段名
            loc = row['location']
            total_freq = row['loc_total_freq']
            # Hover提示：地点+总次数+关联活动
            act_str = ", ".join([f"{act}（{freq}次）" for act, freq in row['activity_type'].items()])
            net_loc_act.add_node(
                f"loc_act_{loc}",  # 前缀区分，避免与人物-地点图谱ID冲突
                label=f"{loc}\n（{total_freq}次）",
                size=25 + total_freq * 2,  
                color="#591F24", 
                title=f"地点：{loc}\n总出现次数：{total_freq}次\n关联活动：{act_str}"
            )  
        #2. 添加活动类型节点
        act_stats_loc = net_df_loc_act.groupby('activity_type').agg({
            'location': lambda x: list(set(x)),
            'loc_total_freq': 'sum'
        }).reset_index()
        act_stats_loc['related_loc_count'] = act_stats_loc['location'].apply(len)
        for _, row in act_stats_loc.iterrows():
            act = row['activity_type']
            loc_count = row['related_loc_count']
            # Hover提示：活动+关联地点数+具体地点
            loc_str = ", ".join(row['location'])
            net_loc_act.add_node(
                f"act_loc_{act}", 
                label=f"{act}\n（{loc_count}地）",
                size=20 + loc_count * 3,  # 大小随关联地点数变化
                color="#ebbcbf",  
                title=f"活动类型：{act}\n关联地点数：{loc_count}个\n涉及地点：{loc_str}"
            )
        #3.添加地点-活动边（灰色，粗细=活动在该地点的频次）
        edge_stats_loc = net_df_loc_act.groupby(['location', 'activity_type'])['loc_total_freq'].sum().reset_index()
        edge_stats_loc.columns = ['location', 'activity_type', 'edge_freq']
        for _, row in edge_stats_loc.iterrows():
            loc_id = f"loc_act_{row['location']}"
            act_id = f"act_loc_{row['activity_type']}"
            edge_width = 2 + (row['edge_freq'] / edge_stats_loc['edge_freq'].max()) * 6  # 粗细随频次变化
            # Hover提示：地点-活动+频次+涉及章回
            related_chapters = sorted(net_df_loc_act[
                (net_df_loc_act['location'] == row['location']) & 
                (net_df_loc_act['activity_type'] == row['activity_type'])
            ]['chapter'].unique())
            chapter_str = ", ".join(map(str, related_chapters))
            net_loc_act.add_edge( #边
                loc_id, act_id,
                color="#7f8c8d", 
                width=edge_width,
                title=f"{row['location']} ↔ {row['activity_type']}\n频次：{row['edge_freq']}次\n章回：{chapter_str}"
            )
        
        #4.布局与交互设置
        net_loc_act.barnes_hut(gravity=-2500, spring_length=200)  
        net_loc_act.show_buttons(["physics", "nodes", "edges"]) 
        
        st.subheader("活动-地点关联图谱")
        #5.临时文件加载,避免本地路径问题
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            net_loc_act.save_graph(f.name)
            with open(f.name, "r", encoding="utf-8") as f_html:
                components.html(f_html.read(), width="100%", height=600, scrolling=False)
        
        #6.图谱说明
        st.caption("深色=地点（大小=总出现次数）" \
        "浅色=活动类型（大小=关联地点数）" \
        "边粗细=活动在该地点频次")

# tab3-各种统计表

with tab3:
    st.title("《儒林外史》地点-人物-活动类型统计表")
    st.caption("侧边栏选择可查看地点、人物、活动分别统计表格")
    #表格呈现 把原表格拆开重新统计
    st.sidebar.header("统计筛选条件")
    # 1. 统计维度选择
    stat_dimension = st.sidebar.radio(
        "选择统计维度",
        ["按地点统计", "按人物统计", "按活动类型统计"]
    )
    # 2. 章回范围筛选，来自df['chapter']的最值）
    min_chapter = int(df['chapter'].min())
    max_chapter = int(df['chapter'].max())
    selected_chapters_stat = st.sidebar.slider(
        "选择章回范围", 
        min_value=min_chapter, 
        max_value=max_chapter, 
        value=(min_chapter, max_chapter),
        key="stat_chapter_slider" 
    )
    
    # 应用章回筛选，先筛选指定章回范围的数据
    stat_df = df[
        (df['chapter'] >= selected_chapters_stat[0]) &
        (df['chapter'] <= selected_chapters_stat[1])
    ].copy()  # 复制数据，避免修改原df
    
    # 按不同维度生成统计表格
    if stat_dimension == "按地点统计":
        st.subheader(f"按地点统计（第{selected_chapters_stat[0]}-{selected_chapters_stat[1]}回）")
        # 1. 按“地点+章回”分组，取每组首次出现的行（确保每个地点在每个章回只统计1次）
        loc_chapter_first = stat_df.groupby(['location', 'chapter']).first().reset_index()
        # 2. 按“地点”分组，求和首次出现的loc_total_freq（得到每个地点的总次数）
        loc_total_freq = loc_chapter_first.groupby('location')['loc_total_freq'].sum().reset_index()
        loc_total_freq.columns = ['location', '总出现次数']  # 重命名列，便于后续合并
        
        # 3. 统计其他维度信息（涉及章回、关联人物、活动类型等）
        loc_other_stats = stat_df.groupby('location').agg({
            # 涉及章回：去重后格式化为“X回（回次1, 回次2）”
            'chapter': lambda x: f"{len(set(x))}回（{', '.join(map(str, sorted(set(x))))}）",
            # 关联人物：拆分多人物、去重后合并
            'characters': lambda x: ', '.join(list(set([
                c.strip() for chars in x.dropna() for c in chars.split('，')
            ])) or ['无']),
            # 活动类型：统计每种活动的次数，生成字典
            'activity_type': lambda x: x.value_counts().to_dict(),
            # 情节示例，取第一条非空情节的前100字
            'plot_summary': lambda x: next((p[:100] + "..." for p in x.dropna() if p), "无相关情节")
        }).reset_index()
        
        # 4. 合并“总出现次数”与其他统计信息
        loc_stat_table = loc_other_stats.merge(loc_total_freq, on='location', how='left')
        loc_stat_table['活动类型统计'] = loc_stat_table['activity_type'].apply(
            lambda x: ", ".join([f"{act}（{freq}次）" for act, freq in x.items()])
        )
        display_table = loc_stat_table[
            ['location', '总出现次数', 'chapter', 'characters', '活动类型统计', 'plot_summary']
        ].rename(columns={
            'location': '地点',
            'chapter': '涉及章回',
            'characters': '关联人物',
            'plot_summary': '情节示例'
        })
        st.dataframe(display_table, height=400)

    elif stat_dimension == "按人物统计":
        # 按人物统计
        st.subheader(f"按人物统计（第{selected_chapters_stat[0]}-{selected_chapters_stat[1]}回）")
        char_stat_list = []
        for _, row in stat_df.iterrows():
            # 拆分多人物（处理“，”分隔的情况）
            chars = [c.strip() for c in row['characters'].split('，')] if pd.notna(row['characters']) else []
            for char in chars:
                char_stat_list.append({
                    '人物': char,
                    '涉及章回': row['chapter'],
                    '关联地点': row['location'],
                    '参与活动': row['activity_type'],
                    '情节': row['plot_summary'][:60] + "..." if pd.notna(row['plot_summary']) else "无相关情节"
                })
        # 去重后按人物分组统计
        char_stat_df = pd.DataFrame(char_stat_list).drop_duplicates()
        char_stat_table = char_stat_df.groupby('人物').agg({
            '涉及章回': lambda x: f"{len(set(x))}回（{', '.join(map(str, sorted(set(x))))}）",
            '关联地点': lambda x: ', '.join(list(set(x)) or ['无']),
            '参与活动': lambda x: x.value_counts().to_dict(),
            '情节': lambda x: x.iloc[0] if not x.empty else "无相关情节"
        }).reset_index()
        # 格式化活动统计
        char_stat_table['参与活动统计'] = char_stat_table['参与活动'].apply(
            lambda x: ", ".join([f"{act}（{freq}次）" for act, freq in x.items()])
        )
        # 显示表格
        display_table = char_stat_table[['人物', '涉及章回', '关联地点', '参与活动统计', '情节']]
        st.dataframe(display_table, height=400)
    
    else:  # 按活动类型统计
        st.subheader(f"按活动类型统计（第{selected_chapters_stat[0]}-{selected_chapters_stat[1]}回）")
        # 统计活动类型的基础信息
        act_stat_table = stat_df.groupby('activity_type').agg({
            'chapter': lambda x: f"{len(set(x))}回（{', '.join(map(str, sorted(set(x))))}）",
            'location': lambda x: ', '.join(list(set(x)) or ['无']),
            'characters': lambda x: ', '.join(list(set([
                c.strip() for chars in x.dropna() for c in chars.split('，')
            ])) or ['无']),
            'plot_summary': lambda x: next((p[:80] + "..." for p in x.dropna() if p), "无相关情节")
        }).reset_index()
        # 计算活动总次数（去重“活动类型+章回”，避免重复统计）
        act_freq = stat_df.groupby(['activity_type', 'chapter']).first().reset_index()
        act_freq = act_freq['activity_type'].value_counts().reset_index()
        act_freq.columns = ['activity_type', '活动总次数']
        # 合并总次数与基础信息
        act_stat_table = act_stat_table.merge(act_freq, on='activity_type', how='left')
        display_table = act_stat_table[
            ['activity_type', '活动总次数', 'chapter', 'location', 'characters', 'plot_summary']
        ].rename(columns={
            'activity_type': '活动类型',
            'chapter': '涉及章回',
            'location': '关联地点',
            'characters': '关联人物',
            'plot_summary': '情节示例'
        })
        st.dataframe(display_table, height=400)
