"""Physical finger collision surfaces; disabled geometric markers for task FK only."""
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
from pathlib import Path
import json
PADS=('right_thumb_fingertip','right_index_fingertip','right_middle_fingertip')
DISTAL=('right_hand_thumb_2_link','right_hand_index_1_link','right_hand_middle_1_link')

def configure(robot):
    original_inertials={b.get('name'):ET.tostring(b.find('inertial')) for b in robot.iter('body') if b.get('name','').startswith(('right_hand_','left_hand_')) and b.find('inertial') is not None}
    pads={g.get('name'):g for g in robot.iter('geom') if g.get('name') in PADS}
    audit=[]
    for b in robot.iter('body'):
        bn=b.get('name','')
        if not bn.startswith(('right_hand_','left_hand_')):continue
        for g in b.findall('geom'):
            name=g.get('name','')
            if 'fingertip' in name:
                g.set('type','sphere');g.set('size','0.0001');g.set('contype','0');g.set('conaffinity','0');g.set('density','0');g.set('group','4')
                audit.append({'body':bn,'name':name,'role':'noncontact FK marker'});continue
            # Original visual copies explicitly disable collision. Preserve their role.
            if g.get('contype')=='0':
                g.set('conaffinity','0');continue
            g.set('name','physical_'+bn);g.set('contype','2');g.set('conaffinity','3')
            audit.append({'body':bn,'name':g.get('name'),'role':'physical finger surface','type':g.get('type','mesh' if g.get('mesh') else 'sphere')})
    assert len([a for a in audit if a['body'].startswith('right_hand_') and a['role']=='physical finger surface'])==7
    for b in robot.iter('body'):
        if b.get('name') in original_inertials:assert ET.tostring(b.find('inertial'))==original_inertials[b.get('name')]
    return audit

def calibrate_markers(robot,path):
    """Use collision mesh geometry to place each nonphysical marker on its actual tip."""
    robot.write(path,encoding='utf-8')
    m=mujoco.MjModel.from_xml_path(str(path));d=mujoco.MjData(m);mujoco.mj_forward(m,d)
    details=[]
    for marker,bn in zip(PADS,DISTAL):
        bid=m.body(bn).id;gid=m.geom('physical_'+bn).id
        if m.geom_type[gid]==mujoco.mjtGeom.mjGEOM_MESH:
            mid=int(m.geom_dataid[gid]);v=m.mesh_vert[m.mesh_vertadr[mid]:m.mesh_vertadr[mid]+m.mesh_vertnum[mid]].copy()
            world=v@d.geom_xmat[gid].reshape(3,3).T+d.geom_xpos[gid]
            local=(world-d.xpos[bid])@d.xmat[bid].reshape(3,3)
        else:
            raise ValueError('Expected original distal collision mesh')
        old=np.fromstring(robot.find(".//geom[@name='%s']"%marker).get('pos','0 0 0'),sep=' ')
        near=local[np.argmin(np.linalg.norm(local-old,axis=1))]
        # Inward-facing pad surface near the original pad region, not the distal end cap.
        long_axis=1 if 'thumb' in bn else 0
        normal_axis=0 if 'thumb' in bn else 1
        band=abs(local[:,long_axis]-old[long_axis])<.010
        assert band.any()
        patch=local[band];point=patch.mean(axis=0)
        point[long_axis]=old[long_axis]
        point[normal_axis]=patch[:,normal_axis].max()
        point[2]=0.
        normal=np.zeros(3);normal[normal_axis]=1.
        robot.find(".//geom[@name='%s']"%marker).set('pos',' '.join(format(float(x),'.12g') for x in point))
        details.append({'marker':marker,'body':bn,'old_point_m':old.tolist(),'actual_mesh_bounds_m':[local.min(axis=0).tolist(),local.max(axis=0).tolist()],'nearest_vertex_m':near.tolist(),'surface_marker_m':point.tolist(),'physical_geom':'physical_'+bn,'mesh_vertices':len(local),'outward_normal_body':normal.tolist()})
    robot.write(path,encoding='utf-8');return details

def finger_contacts(m):
    groups={};geoms=[]
    for g in range(m.ngeom):
        name=m.geom(g).name or '';bn=m.body(int(m.geom_bodyid[g])).name or ''
        if bn.startswith('right_hand_') and int(m.geom_contype[g])!=0:
            assert name.startswith('physical_') and m.geom_type[g]!=mujoco.mjtGeom.mjGEOM_SPHERE
            group=0 if 'thumb' in bn else 1 if 'index' in bn else 2 if 'middle' in bn else None
            assert group is not None;groups[g]=group;geoms.append(g)
    assert len(geoms)==7
    for p in PADS:assert m.geom_contype[m.geom(p).id]==0 and m.geom_conaffinity[m.geom(p).id]==0
    return groups,geoms
