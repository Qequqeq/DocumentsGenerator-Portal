# -*- coding: utf-8 -*-
"""Порт legacy src/getWorkerRisks.py + src/generate_cards.py."""
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from docxtpl import DocxTemplate

from app.modules.projects.risk_math import dangers_list, summary_level
from app.modules.projects.repositories import ProjectRepository


@dataclass
class RiskTpl:
    risk_number: str
    risk_name: str
    degree: int
    degree_info: str
    chance: int
    chance_info: str
    coefficient: float
    coefficient_info: str
    summary: float
    summary_info: str
    danger_group_number: str
    danger_group_name: str
    management_measures: List[str] = field(default_factory=list)


@dataclass
class DangerTpl:
    danger_number: str
    danger_name: str
    summary: float
    risks: List[RiskTpl] = field(default_factory=list)


@dataclass
class WorkerTpl:
    ID: str
    position: str
    division: List[str]
    number_at_workplace: int
    woman: int
    minors: int
    disabled: int
    equipment: str
    materials: str
    workerTotal: float = 0.0
    summary_info: str = ""
    workerDangers: List[DangerTpl] = field(default_factory=list)


@dataclass
class ChairmanTpl:
    position: str
    full_name: str


@dataclass
class OrgTpl:
    full_name: str
    adres: str
    inn: str
    okpo: str
    okogy: str
    okved: str
    oktmo: str
    auditor: ChairmanTpl
    leader: ChairmanTpl
    chairman: ChairmanTpl
    com_members: List[ChairmanTpl] = field(default_factory=list)


def build_org(org_data: dict) -> OrgTpl:
    poses = org_data.get("chairmen_poses") or []
    names = org_data.get("chairmen_names") or []
    com_members = [
        ChairmanTpl(
            position=poses[i] if i < len(poses) else "",
            full_name=names[i] if i < len(names) else "",
        )
        for i in range(max(len(poses), len(names)))
    ]
    return OrgTpl(
        full_name=org_data.get("full_name", ""),
        adres=org_data.get("address", ""),
        inn=org_data.get("inn", ""),
        okpo=org_data.get("okpo", ""),
        okogy=org_data.get("okogy", ""),
        okved=org_data.get("okved", ""),
        oktmo=org_data.get("oktmo", ""),
        auditor=ChairmanTpl(org_data.get("auditor_pos", ""), org_data.get("auditor_name", "")),
        leader=ChairmanTpl(org_data.get("leader_pos", ""), org_data.get("leader_name", "")),
        chairman=ChairmanTpl(org_data.get("chairman_pos", ""), org_data.get("chairman_name", "")),
        com_members=com_members,
    )


def build_worker(w: dict) -> WorkerTpl:
    return WorkerTpl(
        ID=str(w.get("ID", "")),
        position=w.get("position", ""),
        division=list(w.get("division") or []),
        number_at_workplace=int(w.get("number_at_workplace", 0)),
        woman=int(w.get("woman", 0)),
        minors=int(w.get("minors", 0)),
        disabled=int(w.get("disabled", 0)),
        equipment=w.get("equipment", ""),
        materials=w.get("materials", ""),
    )


def compute_worker_risks(
    worker: WorkerTpl,
    dangers: List[dict],
    inputs: Dict,
    eff: Dict,
    measures_map: Dict,
) -> WorkerTpl:
    work_total = 0.0
    for danger in dangers:
        dn = danger["danger_number"]
        cur_risks: List[RiskTpl] = []
        sm = 0.0
        for risk in danger["risks"]:
            rn = risk["risk_number"]
            data = (inputs or {}).get(dn, {}).get(rn, {})
            deg = int(data.get("degree", 0))
            if deg == 0:
                continue
            ch = int(data.get("chance", 1))
            kef = float(data.get("coeff", 0.1))
            res = deg * ch * kef
            if res != 0:
                cur_risks.append(RiskTpl(
                    risk_number=rn,
                    risk_name=risk["risk_name"],
                    degree=deg,
                    degree_info=eff["DEGREE_INFO"].get(deg, ""),
                    chance=ch,
                    chance_info=eff["CHANCE_INFO"].get(ch, ""),
                    coefficient=kef,
                    coefficient_info=eff["COEFF_INFO"].get(kef, ""),
                    summary=res,
                    summary_info=summary_level(res, eff["SUMMARY_INFO"]),
                    danger_group_number=dn,
                    danger_group_name=danger["danger_name"],
                    management_measures=measures_map.get(rn, []),
                ))
                sm += res
        if cur_risks:
            worker.workerDangers.append(DangerTpl(
                danger_number=dn,
                danger_name=danger["danger_name"],
                summary=sm,
                risks=cur_risks,
            ))
            work_total += sm
    worker.workerTotal = work_total
    worker.summary_info = summary_level(work_total, eff["SUMMARY_INFO"])
    return worker


def generate_worker_card(
    template_path: Path,
    doc_date: str,
    org: OrgTpl,
    worker: WorkerTpl,
    output_dir: Path,
    eff: Dict,
) -> Path:
    doc = DocxTemplate(str(template_path))

    danger_groups_list = []
    for danger_tpl in worker.workerDangers:
        items_list = []
        for risk_tpl in danger_tpl.risks:
            appl = summary_level(risk_tpl.summary, eff["SUMMARY_INFO_APLICATION"])
            items_list.append({
                "code": risk_tpl.risk_number,
                "name": risk_tpl.risk_name,
                "st": risk_tpl.degree,
                "st_info": risk_tpl.degree_info,
                "ch": risk_tpl.chance,
                "ch_info": risk_tpl.chance_info,
                "kef": str(risk_tpl.coefficient).replace('.', ','),
                "kef_info": risk_tpl.coefficient_info,
                "sum": f"{risk_tpl.summary:.1f}".replace('.', ','),
                "total_let": appl[:1],
                "total_text": appl[2:],
            })
        danger_groups_list.append({
            "group_id": danger_tpl.danger_number,
            "group_name": danger_tpl.danger_name,
            "group_score": f"{danger_tpl.summary:.1f}",
            "risk_list": items_list,
        })

    comission = [{"name": m.full_name} for m in org.com_members]

    stop_idx = len(danger_groups_list)
    for i in range(1, len(danger_groups_list)):
        if danger_groups_list[i]["group_id"] == "1":
            stop_idx = i
            break
    danger_groups_list = danger_groups_list[:stop_idx]

    context = {
        'organizationName': org.full_name,
        'organizationAdres': org.adres,
        'organizationLead': org.leader.full_name,
        'INN': org.inn,
        'OKPO': org.okpo,
        'OKOGY': org.okogy,
        'OKVED': org.okved,
        'OKTMO': org.oktmo,
        'workNameID': worker.ID,
        'workNamePos': worker.position,
        'workNameNumber': worker.number_at_workplace,
        'workNameWoman': worker.woman,
        'workNameMinor': worker.minors,
        'workNameDisabled': worker.disabled,
        'equipment_list': [i.strip() for i in worker.equipment.split(',')] if worker.equipment else [],
        'materials_list': [i.strip() for i in worker.materials.split(',')] if worker.materials else [],
        'danger_groups': danger_groups_list,
        'TOTAL': f"{worker.workerTotal:.1f}".replace('.', ','),
        'com_chairman': org.chairman.full_name,
        'RiskKlass': worker.summary_info,
        'controlInfo': eff["CONTROL_INFO"].get(worker.summary_info, ""),
        'documentDate': doc_date,
        'comission': comission,
        'division': worker.division,
        'auditor_name': org.auditor.full_name,
    }
    doc.render(context)

    safe_position = re.sub(r'[\/*?:"<>|]', '', worker.position)
    safe_position = ' '.join(safe_position.split())
    if len(safe_position) > 100:
        safe_position = safe_position[:100].rstrip()
    filename = f"Карта{worker.ID}{safe_position}.docx"
    doc.save(output_dir / filename)
    return output_dir / filename



def generate_report(
    report_template_path: Path,
    output_dir: Path,
    org: OrgTpl,
    people: List[WorkerTpl],
    doc_date: str,
    eff: Dict,
) -> Path:
    def risk_in_list(risk, lst):
        return any(r['number'] == risk['number'] and r['name'] == risk['name'] for r in lst)

    def danger_in_list(dang, lst):
        for d in lst:
            if d['group_id'] == dang['group_id'] and d['group_name'] == dang['group_name']:
                existing = [r['number'] for r in d['risk_list']]
                for risk in dang['risk_list']:
                    if risk['number'] not in existing:
                        d['risk_list'].append(risk)
                return True
        return False

    dangers_list_out = []
    for w in people:
        for d in w.workerDangers:
            risk_list = []
            for r in d.risks:
                if r.summary > 0:
                    info = {'number': r.risk_number, 'name': r.risk_name, 'fix': r.management_measures}
                    if not risk_in_list(info, risk_list):
                        risk_list.append(info)
            danger_info = {'group_id': d.danger_number, 'group_name': d.danger_name, 'risk_list': risk_list}
            if not dangers_list_out:
                dangers_list_out.append(danger_info)
            if not danger_in_list(danger_info, dangers_list_out):
                dangers_list_out.append(danger_info)

    dangers_list_out.sort(key=lambda x: [int(p) for p in str(x['group_id']).split('.') if p.isdigit()])
    for dang in dangers_list_out:
        dang['risk_list'].sort(key=lambda x: int(''.join(x['number'].split('.'))))

    totals = {
        'totalWorkPlaces': 0, 'totalWorkers': 0, 'totalWoman': 0, 'totalMinor': 0, 'totalDisabled': 0,
    }
    for letter in ('E', 'D', 'C', 'B', 'A'):
        totals[f'total{letter}'] = 0
        totals[f'totalWorkers{letter}'] = 0
        totals[f'totalWoman{letter}'] = 0
        totals[f'totalMinor{letter}'] = 0
        totals[f'totalDisabled{letter}'] = 0

    for worker in people:
        totals['totalWorkPlaces'] += worker.number_at_workplace
        totals['totalWorkers'] += worker.number_at_workplace
        totals['totalWoman'] += worker.woman
        totals['totalMinor'] += worker.minors
        totals['totalDisabled'] += worker.disabled
        letter = (worker.summary_info or ' ')[:1]
        if letter in ('E', 'D', 'C', 'B', 'A'):
            totals[f'total{letter}'] += worker.number_at_workplace
            totals[f'totalWorkers{letter}'] += worker.number_at_workplace
            totals[f'totalWoman{letter}'] += worker.woman
            totals[f'totalMinor{letter}'] += worker.minors
            totals[f'totalDisabled{letter}'] += worker.disabled

    pos_summary = []
    for worker in people:
        full_control = eff["CONTROL_INFO"].get(worker.summary_info, "")
        words = full_control.split(" ")
        pos_summary.append({
            'num': worker.ID,
            'name': worker.position,
            'risk': worker.summary_info,
            'total': f"{worker.workerTotal:.1f}".replace('.', ','),
            'control_info': " ".join(words[:2]),
            'div': worker.division,
        })

    all_divisions = []
    for worker in people:
        if worker.division not in all_divisions:
            all_divisions.append(worker.division)
    divisions_summary = [
        {'division': div, 'workers': [w for w in pos_summary if w['div'] == div]}
        for div in all_divisions
    ]

    comission = [{"name": m.full_name, "pos": m.position} for m in org.com_members]

    context = {
        'com_chairman': org.chairman.full_name,
        'organizationName': org.full_name,
        'organizationAdres': org.adres,
        'chairman_pos': org.chairman.position,
        'document_date': doc_date,
        'danger_groups': dangers_list_out,
        'totalWorkPlaces': totals['totalWorkPlaces'],
        'divisions': all_divisions,
        'divisions_summary': divisions_summary,
        'comission': comission,
        'auditor_name': org.auditor.full_name,
        'auditor_pos': org.auditor.position,
    }
    context = context | totals

    doc = DocxTemplate(str(report_template_path))
    doc.render(context)
    report_path = output_dir / "Отчет.docx"
    doc.save(report_path)
    return report_path


async def generate_project_documents(project, db, user_id: int, is_premium: bool) -> Tuple[bool, str, int]:
    from app.modules.settings.service import CustomizationService
    from app.modules.templates.service import TemplateService

    eff = await CustomizationService.get_effective(db, user_id)
    measures_map = await CustomizationService.get_measures(db, user_id)
    card_tpl = await TemplateService.resolve(db, user_id, "card", is_premium)
    rep_tpl = await TemplateService.resolve(db, user_id, "report", is_premium)
    if not card_tpl.exists() or not rep_tpl.exists():
        return False, "templates_missing", 0

    org = build_org(project.org_data or {})
    dangers = dangers_list()

    workers: List[WorkerTpl] = []
    for w in (project.people_data or []):
        wt = build_worker(w)
        inputs = (project.risk_inputs or {}).get(str(w["ID"]), {})
        compute_worker_risks(wt, dangers, inputs, eff, measures_map)
        workers.append(wt)

    project_dir = ProjectRepository.get_project_dir(user_id, project.id)
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    for wt in workers:
        generate_worker_card(card_tpl, project.doc_date or "", org, wt, output_dir, eff)
    generate_report(rep_tpl, output_dir, org, workers, project.doc_date or "", eff)

    zip_path = project_dir / "cards_archive.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for doc_file in sorted(output_dir.glob("Карта*.docx")):
            zipf.write(doc_file, arcname=doc_file.name)
        report_file = output_dir / "Отчет.docx"
        if report_file.exists():
            zipf.write(report_file, arcname="Отчет.docx")

    return True, "", len(workers)