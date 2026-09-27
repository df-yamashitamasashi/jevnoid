import pytest
from src.domain.tierra_vm import TierraVM, TierraOp, ANCESTOR_80_GENOME
from src.domain.organism import Organism
from src.domain.species import SpeciesType
from src.adapters.vital_repo import InMemoryVitalRepository
from src.adapters.jev_brain import JevBrain
from src.adapters.web_forager import WebForager
from src.usecases.heartbeat import HeartbeatUsecase


def test_tierra_vm_ancestor_initialization():
    vm = TierraVM.create_with_ancestor(soup_size=512, start_address=16)
    assert vm.soup_size == 512
    assert vm.ip == 16
    assert vm.genome_size == 80
    assert vm.soup[16] == int(TierraOp.NOP_1)


def test_tierra_vm_cycles_and_divide():
    vm = TierraVM.create_with_ancestor(soup_size=512, start_address=32)
    divides = []

    def on_div(count, genome):
        divides.append((count, len(genome)))

    # Award enough cycles for at least 1 full copy loop
    vm.award_cpu_slice(120)
    res = vm.execute_slice(on_divide_callback=on_div)

    assert res["cycles_run"] == 120
    assert vm.total_cycles_executed == 120
    assert len(divides) >= 1
    assert vm.divide_count >= 1


def test_tierra_vm_organism_integration():
    org = Organism.spawn(SpeciesType.GAIA)
    assert org.tierra_vm is not None
    assert org.tierra_vm.genome_size == 80
    assert org.tierra_vm.divide_count == 0


@pytest.mark.asyncio
async def test_heartbeat_tierra_cpu_award():
    repo = InMemoryVitalRepository()
    brain = JevBrain()
    forager = WebForager(timeout_sec=1.0)
    uc = HeartbeatUsecase(repo=repo, brain=brain, forager=forager)

    # Execute a heartbeat pulse
    res = await uc.pulse_all()
    assert res

    organisms = await repo.get_all_organisms()
    # Check that the pulsed organism executed Tierra CPU cycles
    pulsed_org = [o for o in organisms if o.age_pulses > 0][0]
    assert pulsed_org.tierra_vm.total_cycles_executed > 0


def test_complementary_template_matching():
    from src.domain.tierra_vm import TemplateMatcher
    # Background filled with non-NOP opcode (e.g. 25: MAL)
    soup = [int(TierraOp.MAL)] * 64
    # Pattern at pos 5: NOP_0, NOP_1, NOP_0
    soup[5] = int(TierraOp.NOP_0)
    soup[6] = int(TierraOp.NOP_1)
    soup[7] = int(TierraOp.NOP_0)

    # Complement pattern at pos 20: NOP_1, NOP_0, NOP_1
    soup[20] = int(TierraOp.NOP_1)
    soup[21] = int(TierraOp.NOP_0)
    soup[22] = int(TierraOp.NOP_1)

    template = TemplateMatcher.extract_template(soup, 4)
    assert template == [TierraOp.NOP_0, TierraOp.NOP_1, TierraOp.NOP_0]

    complement = TemplateMatcher.get_complement(template)
    assert complement == [TierraOp.NOP_1, TierraOp.NOP_0, TierraOp.NOP_1]

    # Search forward should find the address after complement (pos 23)
    target = TemplateMatcher.search_forward(soup, 8, complement)
    assert target == 23


def test_parasite_and_diversity_metrics():
    from src.domain.tierra_vm import classify_genome, calculate_diversity_index, PARASITE_45_GENOME
    # Classify canonical parasite
    lineage, diffs = classify_genome(PARASITE_45_GENOME)
    assert "Parasite-45p" in lineage

    # Calculate diversity index with mixed population
    lineages = ["Ancestor-80", "Ancestor-80", "Parasite-45p", "Mutant-Lineage-5β"]
    h_index = calculate_diversity_index(lineages)
    assert h_index > 0.9  # Mixed ecosystem has high Shannon entropy
