import ansa
from ansa import base
from ansa import constants
from ansa import connections
def search_max_pid():
    props = base.CollectEntities(constants.LSDYNA, None, '__PROPERTIES__')
    pid = []
    for prop in props:
        pid.append(list(base.GetEntityCardValues(constants.LSDYNA, prop, {'PID'}).values())[0])
        pid.sort()
    max_pid = pid[-1]    
    return max_pid

def create_contact(type_settings, identification_settings, name):
    # 公共参数字典
    friction_and_stiffness = {
        'FS': 0.2,    # 静摩擦系数
        'FD': 0.2,    # 动摩擦系数
        'DC': 0,      # 直接接触
        'VC': 0,      # 体积压缩
        'VDC': 20,    # 体积压缩刚度
    }

    tolerances = {
        'BT': 0,      # 绑定公差
        'DT': 1.0E20, # 破坏时公差
    }

    safety_factors = {
        'SFS': 1,    # 从属安全系数
        'SFM': 1,    # 主安全系数
        'SST': 0,    # 从属安全类型
        'MST': 0,    # 主安全类型
        'SFST': 1,   # 从属安全强度类型
        'SFMT': 1,   # 主安全强度类型
        'FSF': 1,    # 强度安全因子
        'VSF': 1,    # 体积安全因子
    }
    optional_and_other_settings = {
        'OPTIONAL CARDS A,B,C,D,E': 'A & B & C',
        'SOFT': 1,
        'SOFSCL': 0.1,
        'LCIDAB': 0,
        'MAXPAR': 1.025,
        'FRCFRQ': 1,
        'IGAP': 1,
        'IGNORE': 1,
        'CID_RCF': 0,
    }
    # 合并所有分类词典
    vals = {**type_settings, **identification_settings, **friction_and_stiffness, **tolerances, **safety_factors, **optional_and_other_settings}

    # 创建实体
    ent_contact = base.CreateEntity(constants.LSDYNA, 'CONTACT', vals)
    print(ent_contact)

    # 设置实体名称
    base.SetEntityCardValues(constants.LSDYNA, ent_contact, {'Name': name})

    # 获取实体属性
    fields = ['SSTYP']
    vals = base.GetEntityCardValues(constants.LSDYNA, ent_contact, fields)
    return ent_contact
def create_contact2():
    # 定义不同的配置
    config_1 = {
        'type_settings': {'TYPE': 'TIED_SHELL_EDGE_TO_SURFACE_OFFSET', 'SSTYP': '4: Node set', 'MSTYP': '2: Part set'},
        'identification_settings': {'MBOXID': 0, 'SPR': 1, 'MPR': 1},
        'name': "Connectionforbeams"
    }

    config_2 = {
        'type_settings': {'TYPE': 'TIED_NODES_TO_SURFACE_OFFSET', 'SSTYP': '2: Part set', 'MSTYP': '2: Part set','SSID':10000100,'MSID':10000101},
        'identification_settings': {'SBOXID': 0, 'MBOXID': 0, 'SPR': 1, 'MPR': 1},
        'name': "Connectionforsolids"
    }
    #create_contact(**config_1)
    solid_contact = create_contact(**config_2)
    return solid_contact
def set_createslave():	
	vals = {'SID': '10000100', 'Name': 'For_Solid-connection_S'}
	set = base.CreateEntity(constants.LSDYNA, "SET", vals)
	return set
def set_createmaster():	
	vals = {'SID': '10000101', 'Name': 'For_Solid-connection_M'}
	set = base.CreateEntity(constants.LSDYNA, "SET", vals)
	return set


def main(): 
    #创建接触相关的set
    set_createslave()
    set_createmaster()
    solid_contact = create_contact2()
    #创建焊点实体PID
    max_pid = search_max_pid()
    vals_pid = {'PID': max_pid + 1,  'Name': 'spotweld_for_solid', 'MID': 714}
    ent = base.CreateEntity(constants.LSDYNA, 'SECTION_SOLID', vals_pid)
    #收集所有的PSHELL，建立PID和name的映射关系
    Section_Shells = base.CollectEntities(constants.LSDYNA, None, 'SECTION_SHELL')
    section_shell_set = base.CreateEntity(constants.LSDYNA, 'SET')
    pid_name_dict = {}
    for prop in Section_Shells:
        ret = base.GetEntityCardValues(constants.LSDYNA, prop, ('PID', 'Name'))
        pid = ret['PID']
        name = ret['Name']
        pid_name_dict[pid] = name   
    #收集所有的SpotweldPoint，根据其中的comment信息设置对应的连接属性
    SpotweldPoint_Types = base.CollectEntities(constants.LSDYNA, None, 'SpotweldPoint_Type')
    for SpotWeld in SpotweldPoint_Types:
        SpotWeld_comment = SpotWeld._comment
        names_in_comment = SpotWeld_comment.split(',')
        matching_pids = []
        for name in names_in_comment:
            matching_pids.extend([pid for pid, target_name in pid_name_dict.items() if target_name == name])
        vals = {'P1': '',  'P2': '',  'P3': '',  'P4': '',  'P5': '',  'P6': '',  'P7': '',  'P8': '',  'P9': '',  'P10': ''}
        keys = list(vals.keys())[:len(matching_pids)]
        for key, pid in zip(keys, matching_pids):
            vals[key] = f'#{pid}'
        base.SetEntityCardValues(constants.LSDYNA, SpotWeld, vals)
    #连接部分
    base.SetEntityId(solid_contact, 10000100, True)
    connections.RealizeConnections(SpotweldPoint_Types, {'SpotweldPoint_Type': 'DYNA SPOT WELD','SpotweldPoint_DYNA-SPOT-WELD_Property':'PSOLID','SpotweldPoint_DYNA-SPOT-WELD_PSOLID_ID':ent._id, 'SpotweldPoint_DYNA-SPOT-WELD_NumberOfHexas': '1', 'SpotweldPoint_DYNA-SPOT-WELD_DoNotMove': 'y', 'SpotweldPoint_DYNA-SPOT-WELD_UseMat100': 'n','SpotweldPoint_DYNA-SPOT-WELD_Property_Index': '2', 'SpotweldPoint_DYNA-SPOT-WELD_PSOLID_Definition': 'by ID','SpotweldPoint_DYNA-SPOT-WELD_SearchDist': '15.000000','SpotweldPoint_DYNA-SPOT-WELD_ContactId': solid_contact._id, 'SpotweldPoint_DYNA-SPOT-WELD_ContactDefinition': 'by ID	','SpotweldPoint_DYNA-SPOT-WELD_Contacts': 'y'})
main()
