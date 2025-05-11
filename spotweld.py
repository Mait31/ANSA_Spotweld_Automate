import ansa
import time
import re
import numpy as np
from ansa import base
from ansa import constants
from ansa import connections
from itertools import combinations

#根据ws查找所有焊点，返回WS_Entities    
def Pick_SpotWeld():
    Parts = base.CollectEntities(
        constants.LSDYNA, None, "ANSAPART"
    )
    WS_Entities=[]
    for Part in Parts:
        Part_Name = Part._name
        if "ws" in Part_Name.lower():
            WS_Entities.append(Part)
    return WS_Entities
    
def compare_color(entity, color):
    fields = ['COLOR_R', 'COLOR_G', 'COLOR_B']
    vals = base.GetEntityCardValues(constants.NASTRAN, entity, fields)
    for field in fields:
        if vals[field] != color[field]:
            return False
    return True
    
def check(hunt):
    options = ['NEEDLE FACES', 'SINGLE CONS', 'CRACKS', 'OVERLAPS', 'COLLAPSED CONS', 'UNCHECKED FACES','Problematic Surface']
    fix = [1] * len(options)
    ret = base.CheckAndFixGeometry(hunt, options, fix, True, True)
def PartName2PropNameMain():
    parts = base.CollectEntities(constants.LSDYNA, None, "ANSAPART")
    for part in parts:
        part_name = part._name
        props = base.CollectEntities(constants.LSDYNA,part,"SECTION_SHELL",prop_from_entities=True)
        for prop in props:
            base.SetEntityCardValues(constants.LSDYNA, prop, {"Name":part_name})
def calculate_circumradius(p1, p2, p3):
    """
    计算三角形的外接圆半径。
    :param p1: 第一个点的坐标 (x, y, z)
    :param p2: 第二个点的坐标 (x, y, z)
    :param p3: 第三个点的坐标 (x, y, z)
    :return: 外接圆半径或 None 如果三角形无效
    """
    # 将点转换为 numpy 数组方便计算
    A = np.array(p1)
    B = np.array(p2)
    C = np.array(p3)
    
    # 计算边长
    a = np.linalg.norm(B - C)
    b = np.linalg.norm(A - C)
    c = np.linalg.norm(A - B)
    
    # 检查边长是否有效
    if not (a > 0 and b > 0 and c > 0 and a + b > c and a + c > b and b + c > a):
        return None
    
    # 计算面积 (使用海伦公式)
    s = (a + b + c) / 2
    area = np.sqrt(s * (s - a) * (s - b) * (s - c))
    
    # 计算外接圆半径
    R = (a * b * c) / (4 * area) if area != 0 else float('inf')
    
    return R

def check_points_on_circle(points, known_radius=3.0, atol=0.25):
    """
    检查一组点是否近似位于同一个圆上，已知圆的半径。
    :param points: 点的列表，每个点是一个三维坐标。
    :param known_radius: 已知圆的半径
    :param atol: 绝对容差，允许的最大绝对误差
    :return: 是否满足给定的几何性质
    """
    point_combinations = list(combinations(points, 3))
    all_radii_close = True

    for combo in point_combinations:
        R = calculate_circumradius(*combo)
        if R is None:
            continue
        
        radius_is_close = np.isclose(R, known_radius, atol=atol)
        
        if not radius_is_close:
            all_radii_close = False
            break  # 一旦发现不满足条件的组合，立即返回 False

    return all_radii_close

def filter_close_points(points, threshold):
    """
    过滤掉坐标相近的点，返回过滤后的点列表。
    :param points: 点的列表，每个点是一个三维坐标。
    :param threshold: 距离阈值，小于该阈值的点被认为是相近的。
    :return: 过滤后的点列表。
    """
    filtered_points = []
    for point in points:
        if all(np.linalg.norm(point - p) >= threshold for p in filtered_points):
            filtered_points.append(point)
        # 不再输出调试信息
    return filtered_points

# 优化后的点焊与缝焊分类函数
def classify_weld_types(Part_Parent,WS_Entities):
    seamline = set()
    spot_weld = set()
    processed_faces = set()
    for prop in WS_Entities:
        #print(f"{WS_Entities}中正在处理的PID为{prop._id}")
        base.Or(Part_Parent)
        faces = base.CollectEntities(constants.LSDYNA, prop, "FACE", filter_visible=True)
        color_attributes = ['COLOR_R', 'COLOR_G', 'COLOR_B']
        vals = base.GetEntityCardValues(constants.LSDYNA, prop, color_attributes)
        
        if not faces:
            continue
            
        # 批量处理未处理的面
        unprocessed_faces = [face for face in faces if face not in processed_faces]
        while unprocessed_faces:
            # 取第一个未处理的面作为起点
            start_face = unprocessed_faces[0]
            base.Or(start_face)
            base.Neighb('ALL')
            connected_faces = base.CollectEntities(constants.LSDYNA, None, "FACE", filter_visible=True)
            
            # 为这一组面创建新属性
            prop_new = base.CopyEntity(property, prop)
            base.SetEntityCardValues(constants.LSDYNA, prop_new, vals)
            
            # 为连接的面设置新属性
            for face in connected_faces:
                base.SetEntityCardValues(constants.LSDYNA, face, {"PID": prop_new._id})
                processed_faces.add(face)
            
            # 更新未处理列表
            unprocessed_faces = [face for face in unprocessed_faces if face not in processed_faces]
            
            # 计算判断是点焊还是缝焊
            Cog_Coordinates = base.Cog(prop_new)
            
            Point_nums = base.CollectEntities(constants.LSDYNA, None, "HOT POINT", filter_visible=True)
            
            positions = np.array([point.position for point in Point_nums])
            
            # 设定距离阈值
            distance_threshold = 0.3  # 根据实际情况调整此值
            
            # 过滤相近点
            filtered_positions = filter_close_points(positions, distance_threshold)
            
            # 获取所有三个点的组合
            point_combinations = list(combinations(filtered_positions, 3))
            
            # 检查每个组合是否满足条件
            result = check_points_on_circle(filtered_positions, known_radius=3.0, atol=0.25)
            if not result:
                seamline.add(prop_new)
            else:
                spot_weld.add(prop_new)
    
    # 压缩数据并存储视图
    base.Compress('')   
    return seamline, spot_weld

def Find_ws(Part_Parent,WS_Entity):
    color_yellow = {'COLOR_R': 255, 'COLOR_G': 255, 'COLOR_B': 0}
    color_red = {'COLOR_R': 255, 'COLOR_G': 0, 'COLOR_B': 0}    
    base.Or(Part_Parent)
    #Current_View_WS_Entity存储每一个Part_Parent下的点焊和缝焊数据
    Current_View_WS_Entity = base.CollectEntities(constants.LSDYNA, WS_Entity, "SECTION_SHELL",prop_from_entities=True, filter_visible=True)
    Current_View_Props = base.CollectEntities(constants.LSDYNA, None, "SECTION_SHELL",prop_from_entities=True, filter_visible=True)
    #print(f"初始状态下，{WS_Entity._name}内Pshell数量为{len(Current_View_Props)}",f"其中涉及ws的Pshell数量为{len(Current_View_WS_Entity)}")
    #返回正在遍历的WS_Entity下的所有点焊和缝焊数据        
    seamline, spot_welds = classify_weld_types(Part_Parent,Current_View_WS_Entity)
    #print(f"经过分离PID后，{Part_Parent._name}内缝焊数量为{len(seamline)},点焊数量为{len(spot_welds)}")
    if spot_welds != 0:
        base.Or(Part_Parent)
        base.Not(seamline)
        base.Not(spot_welds)
        other_entity = set()
        for spotweld in spot_welds:
            Cog_Coordinates = base.Cog(spotweld)
            vals = ('P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9','P10')
            ConnectionPoint = connections.CreateConnectionPoint('SpotweldPoint_Type', Cog_Coordinates)
            connections.AutoSetConnectivityInConnections(ConnectionPoint, search_distance=5, filter_visible=True, search_solids=False, search_shells=False, output_mode='pid', find_up_to=10)
            ret = base.GetEntityCardValues(constants.LSDYNA, ConnectionPoint, vals)
            list_vals = list(ret.values())
            #print("list_vals",list_vals)
            list_vals.sort()
            #统计空值数量
            num_empty = list_vals.count('')
            #去除空值
            Ps = list_vals[num_empty:]
            #去重
            set_Ps = {i for i in Ps}
            Ps_noduplicate = [i for i in set_Ps]
            #print("Ps_noduplicate",Ps_noduplicate)
            #print("len(Ps_noduplicate)",len(Ps_noduplicate))
            #print(compare_color(spotweld, color_yellow))
            #print(compare_color(spotweld, color_red))
            if len(Ps_noduplicate) == 2 and compare_color(spotweld, color_yellow):
                pshell_1 = base.GetEntity(ansa.constants.LSDYNA, "SECTION_SHELL", int(Ps_noduplicate[0][1:]))
                pshell_2 = base.GetEntity(ansa.constants.LSDYNA, "SECTION_SHELL", int(Ps_noduplicate[1][1:]))
                comment = f"{pshell_1._name},{pshell_2._name}"
                vals = {'D': 6,  'Name': '',  'Comment': comment,  'P1': Ps_noduplicate[0],  'P2': Ps_noduplicate[1],  'P3': '',  'P4': '',  'P5': '',  'P6': '',  'P7': '',  'P8': '',  'P9': '',  'P10': ''}     
                base.SetEntityCardValues(constants.LSDYNA, ConnectionPoint, vals)
            elif len(Ps_noduplicate) == 3 and compare_color(spotweld, color_red):
                pshell_1 = base.GetEntity(ansa.constants.LSDYNA, "SECTION_SHELL", int(Ps_noduplicate[0][1:]))
                pshell_2 = base.GetEntity(ansa.constants.LSDYNA, "SECTION_SHELL", int(Ps_noduplicate[1][1:]))
                pshell_3 = base.GetEntity(ansa.constants.LSDYNA, "SECTION_SHELL", int(Ps_noduplicate[2][1:]))
                #print(pshell_1,pshell_2,pshell_3) 
                comment = f"{pshell_1._name},{pshell_2._name},{pshell_3._name}"            
                vals = {'D': 6,  'Name': '',  'Comment': comment,  'P1': Ps_noduplicate[0],  'P2': Ps_noduplicate[1],  'P3': Ps_noduplicate[2],  'P4': '',  'P5': '',  'P6': '',  'P7': '',  'P8': '',  'P9': '',  'P10': ''}
                base.SetEntityCardValues(constants.LSDYNA, ConnectionPoint, vals)
            else:
            	other_entity.update({spotweld, ConnectionPoint})
            	pshells = [base.GetEntity(ansa.constants.LSDYNA, "SECTION_SHELL", int(pid[1:])) for pid in Ps_noduplicate]
            	vals = {'D': 6,'Name': ''}
            	for i in range(1, 11):
            		key = f'P{i}'
            		vals[key] = ''
            	for i, pid in enumerate(Ps_noduplicate):
            		key = f'P{i+1}'
            		if key in vals:
            			vals[key] = pid
            	base.SetEntityCardValues(constants.LSDYNA, ConnectionPoint, vals)   	
    return other_entity
                 
def remove_duplicate_weld_points(spot_weld_point):    
    # 对点进行逻辑或操作（确保所有点被选中）
    base.Or(spot_weld_point)
    
    # 去除重复的点
    base.PointsRemoveDouble(entities='visible', tolerance=5)
    Filter_Points = base.CollectEntities(constants.LSDYNA, None, "POINT", filter_visible=True)
    for point in Filter_Points:
        hd = connections.CreateConnectionPoint('SpotweldPoint_Type', point.position)
        base.DeleteEntity(point)
    

def main():
    PartName2PropNameMain()
    #WS_Entities内存储了WS ANSAPart
    WS_Entities=Pick_SpotWeld()
    base.BlockRedraws(True)
    t1 = time.time()
    Not_recognized_SpotWeld = set()
    for WS_Entity in WS_Entities:
        Part_Depth=base.GetPartDepth(WS_Entity)
        #print("结构树内WS_Entity新一轮循环")
        #print(f"Part_Depth:{Part_Depth}")
        #print(base.GetEntityCardValues(constants.LSDYNA, Part_Depth["parent_part"], ("Name",)))
        Part_Parent = Part_Depth['parent_part']
        Find_ws_Result = Find_ws(Part_Parent,WS_Entity)
        Not_recognized_SpotWeld.update(Find_ws_Result)
    #remove_duplicate_weld_points(spot_weld_point)
    base.SetEntityVisibilityValues(constants.LSDYNA, {"SpotweldPoint_Type": "on"})
    base.Or(Not_recognized_SpotWeld)
    lockview = base.StoreLockView('未识别的焊点', True)
    base.Or(WS_Entities)
    base.BlockRedraws(False)
    t2 = time.time()
    print("time continuing: %f" % (t2-t1))
main()
