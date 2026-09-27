    let organismsData = [];
    let currentHabitatIndex = 0; // 0: gaia, 1: theos, 2: cosmo, 3: info
    const SPECIES_ORDER = ["gaia", "theos", "cosmo", "info"];

    // Vitals contain text crawled from arbitrary web pages: every string must be escaped before innerHTML.
    const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => HTML_ESCAPES[ch]);
    }
    function num(value) {
      const n = Number(value);
      return Number.isFinite(n) ? n : 0;
    }

    // Habitat visual profiles: Background fog, particle theme, grid type
    const HABITAT_CONFIGS = {
      "gaia": {
        name: "Gaia-noid (Biosphere)",
        titleBadge: "🌿 HABITAT 1/4 : GAIA-NOID",
        color: "#06d6a0",
        fogColor: 0x020d08,
        particleColor: 0x06d6a0,
        gridColor: 0x0a2618,
        telos: "Planetary ecosystem and climate intelligence assimilation",
        description: "Living terrarium filled with primordial forest spores and photosynthetic energy"
      },
      "theos": {
        name: "Theos-noid (Divinity)",
        titleBadge: "✦ HABITAT 2/4 : THEOS-NOID",
        color: "#ffd166",
        fogColor: 0x0d0902,
        particleColor: 0xffd166,
        gridColor: 0x2b2106,
        telos: "Theological exploration and reconciliation of love and transcendence",
        description: "Celestial celestial sphere wrapped in sacred light particles and golden auras"
      },
      "cosmo": {
        name: "Cosmo-noid (Deep Space)",
        titleBadge: "🌌 HABITAT 3/4 : COSMO-NOID",
        color: "#b5179e",
        fogColor: 0x0b020e,
        particleColor: 0xb5179e,
        gridColor: 0x290533,
        telos: "Cosmological physics, quantum mechanics, and entropy law assimilation",
        description: "Vacuum singularity terrarium drifting with interstellar dust and spacetime warps"
      },
      "info": {
        name: "Info-Grazer (Pure Data)",
        titleBadge: "⚡ HABITAT 4/4 : INFO-GRAZER",
        color: "#4cc9f0",
        fogColor: 0x010c14,
        particleColor: 0x4cc9f0,
        gridColor: 0x042436,
        telos: "Compilation of academic literature and objective knowledge networks",
        description: "Cyber terrarium intersecting with high-speed data streams and knowledge lattices"
      }
    };

    // --- Three.js Isolated Multi-Habitat Setup ---
    const container = document.getElementById("canvas-3d-container");
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020d08, 0.006);

    const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 30, 75);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxDistance = 200;
    controls.minDistance = 15;

    // Ambient and Point Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.45);
    scene.add(ambientLight);

    const mainPointLight = new THREE.PointLight(0x06d6a0, 1.4, 250);
    mainPointLight.position.set(0, 40, 40);
    scene.add(mainPointLight);

    // Floor Habitat Grid
    const gridHelper = new THREE.GridHelper(80, 20, 0x06d6a0, 0x0a2618);
    gridHelper.position.y = -22;
    scene.add(gridHelper);

    // Habitat Environment Particle System
    const particleGeo = new THREE.BufferGeometry();
    const particleCount = 450;
    const particlePositions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount * 3; i += 3) {
      particlePositions[i] = (Math.random() - 0.5) * 200;
      particlePositions[i + 1] = (Math.random() - 0.5) * 120;
      particlePositions[i + 2] = (Math.random() - 0.5) * 200;
    }
    particleGeo.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
    const particleMat = new THREE.PointsMaterial({
      color: 0x06d6a0,
      size: 1.4,
      transparent: true,
      opacity: 0.65
    });
    const habitatParticles = new THREE.Points(particleGeo, particleMat);
    scene.add(habitatParticles);

    // Central 3D Group for the currently active organism
    const activeOrganismGroup = new THREE.Group();
    scene.add(activeOrganismGroup);

    // Resize handler
    window.addEventListener("resize", () => {
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    });

    // Keyboard navigation (Left / Right Arrow)
    window.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") prevHabitat();
      if (e.key === "ArrowRight") nextHabitat();
    });

    // Step camera distance along its current viewing direction, for setups without scroll/pinch zoom.
    function zoomBy(factor) {
      const dir = camera.position.clone().sub(controls.target);
      const dist = dir.length();
      if (dist < 1e-6) return;
      const clamped = Math.min(controls.maxDistance, Math.max(controls.minDistance, dist * factor));
      camera.position.copy(controls.target).add(dir.normalize().multiplyScalar(clamped));
      controls.update();
    }

    document.addEventListener("click", (e) => {
      const target = e.target.closest("[data-nav], [data-habitat], [data-org-id], [data-toggle], [data-view], [data-zoom]");
      if (!target) {
        closeArchiveMenu();
        return;
      }
      if (target.dataset.nav === "prev") prevHabitat();
      else if (target.dataset.nav === "next") nextHabitat();
      else if (target.dataset.habitat !== undefined) selectHabitat(num(target.dataset.habitat));
      else if (target.dataset.orgId) selectOrganism(target.dataset.orgId);
      else if (target.dataset.toggle === "archive-menu") toggleArchiveMenu();
      else if (target.dataset.view) setViewSource(target.dataset.view);
      else if (target.dataset.zoom === "in") zoomBy(0.8);
      else if (target.dataset.zoom === "out") zoomBy(1.25);
    });

    // Flag: set true whenever organisms are redrawn so the anim loop fits the camera
    let needsFit = false;

    // 3D Animation Render Loop
    function animate3D() {
      requestAnimationFrame(animate3D);
      controls.update();

      // Slow environmental rotation of particles
      habitatParticles.rotation.y += 0.0003;

      // Respiration pulsation of the living organism
      const time = performance.now() * 0.0018;
      activeOrganismGroup.rotation.y = Math.sin(time * 0.3) * 0.06;

      // Smoothly fit camera to all organisms every frame until converged
      if (needsFit) {
        needsFit = !_fitCameraStep();
      }

      renderer.render(scene, camera);
    }
    animate3D();

    // Tierra Colony Multi-Organism State
    let selectedOrganismId = null;

    function getActiveColony() {
      const activeSpecies = SPECIES_ORDER[currentHabitatIndex];
      return organismsData.filter(o => o.species === activeSpecies && o.is_alive !== false);
    }

    function getSelectedOrganism() {
      const colony = getActiveColony();
      if (!colony || colony.length === 0) return null;
      if (!selectedOrganismId) return colony[0];
      const found = colony.find(o => o.id === selectedOrganismId);
      return found || colony[0];
    }

    function selectOrganism(orgId) {
      selectedOrganismId = orgId;
      renderActiveOrganismMorphology();
      updateSpotlightCard();
    }

    // Spatial cluster offsets for organisms co-inhabiting the same world
    const COLONY_OFFSETS = [
      new THREE.Vector3(0, 0, 0),        // Ancestor / Host
      new THREE.Vector3(26, 3, 14),      // Offspring / Sub-lineage 1
      new THREE.Vector3(-26, -4, 16),    // Offspring / Sub-lineage 2
      new THREE.Vector3(0, 18, -20),     // Offspring / Sub-lineage 3
    ];
    const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

    // Beyond the four hand-placed slots, spiral outward so any colony size gets distinct positions.
    function colonyOffset(index) {
      if (index < COLONY_OFFSETS.length) return COLONY_OFFSETS[index];
      const radius = 30 + 5 * Math.sqrt(index);
      const theta = index * GOLDEN_ANGLE;
      return new THREE.Vector3(radius * Math.cos(theta), ((index % 3) - 1) * 12, radius * Math.sin(theta));
    }

    // Fixed ASCII formats in the viewer's local time zone: locale-aware formatting would show
    // non-Latin scripts (e.g. "2026年9月27日") and break the terminal aesthetic.
    const pad2 = n => String(n).padStart(2, "0");
    function formatClock(date) {
      return `${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`;
    }
    function formatTimeZone(date) {
      const offsetMin = -date.getTimezoneOffset();
      const sign = offsetMin >= 0 ? "+" : "-";
      const h = Math.floor(Math.abs(offsetMin) / 60), m = Math.abs(offsetMin) % 60;
      return `GMT${sign}${h}${m ? ":" + pad2(m) : ""}`;
    }

    function formatBirth(bornAt) {
      const born = new Date(bornAt);
      if (!bornAt || Number.isNaN(born.getTime())) return { absolute: "Unknown", relative: "" };
      const minutes = Math.max(0, Math.floor((Date.now() - born.getTime()) / 60000));
      const days = Math.floor(minutes / 1440), hours = Math.floor((minutes % 1440) / 60), mins = minutes % 60;
      const relative = days > 0 ? `${days}d ${hours}h ago` : hours > 0 ? `${hours}h ${mins}m ago` : `${mins}m ago`;
      const date = `${born.getFullYear()}-${pad2(born.getMonth() + 1)}-${pad2(born.getDate())}`;
      return {
        absolute: `${date} ${pad2(born.getHours())}:${pad2(born.getMinutes())} ${formatTimeZone(born)}`,
        relative,
      };
    }

    // Rebuild 3D Meshes for All Living Organisms in Current World
    function renderActiveOrganismMorphology() {
      const colony = getActiveColony();
      const selectedOrg = getSelectedOrganism();

      // Clear existing meshes
      while (activeOrganismGroup.children.length > 0) {
        const obj = activeOrganismGroup.children[0];
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) obj.material.dispose();
        activeOrganismGroup.remove(obj);
      }

      if (!colony || colony.length === 0) return;

      const parasiteCenter = null;
      let hostCenter = null;

      colony.forEach((org, orgIdx) => {
        if (!org.morphology || !org.morphology.cells) return;
        const offset = colonyOffset(orgIdx);
        const isSelected = selectedOrg && selectedOrg.id === org.id;
        const isParasite = (org.lineage || "").toLowerCase().includes("parasite");
        // Glow brightness doubles as an energy readout: a starving organism visibly dims.
        const energyGlow = 0.25 + 0.75 * Math.max(0, Math.min(100, num(org.energy))) / 100;

        if (orgIdx === 0) hostCenter = offset.clone();

        const cellPosMap = new Map();

        // 1. Draw Cell Nodes for this organism
        org.morphology.cells.forEach(c => {
          const globalPos = new THREE.Vector3(c.x + offset.x, c.y + offset.y, c.z + offset.z);
          cellPosMap.set(c.id, globalPos);

          const radius = (c.radius || 1.2) * (isSelected ? 1.08 : 0.95);
          const sphereGeo = new THREE.SphereGeometry(radius, 24, 24);
          const baseColor = new THREE.Color(c.color || org.theme_color);

          const sphereMat = new THREE.MeshStandardMaterial({
            color: baseColor,
            roughness: 0.25,
            metalness: 0.35,
            emissive: baseColor,
            emissiveIntensity: (c.id === "cell-origin" ? (isSelected ? 0.95 : 0.65) : (isSelected ? 0.45 : 0.25)) * energyGlow,
          });

          const sphereMesh = new THREE.Mesh(sphereGeo, sphereMat);
          sphereMesh.position.copy(globalPos);
          activeOrganismGroup.add(sphereMesh);

          // Origin breathing halo
          if (c.id === "cell-origin") {
            const glowGeo = new THREE.SphereGeometry(radius * (isSelected ? 2.0 : 1.6), 16, 16);
            const glowMat = new THREE.MeshBasicMaterial({
              color: baseColor,
              transparent: true,
              opacity: (isSelected ? 0.35 : 0.18) * energyGlow,
              wireframe: true,
            });
            const glowMesh = new THREE.Mesh(glowGeo, glowMat);
            glowMesh.position.copy(globalPos);
            activeOrganismGroup.add(glowMesh);
          }
        });

        // 2. Draw Structural Fibers / Bones
        if (org.morphology.edges) {
          org.morphology.edges.forEach(edge => {
            const p1 = cellPosMap.get(edge.source_id);
            const p2 = cellPosMap.get(edge.target_id);
            if (!p1 || !p2) return;

            const edgeGeo = new THREE.BufferGeometry().setFromPoints([p1, p2]);
            const edgeMat = new THREE.LineBasicMaterial({
              color: new THREE.Color(org.theme_color),
              transparent: true,
              opacity: isSelected ? 0.75 : 0.4,
              linewidth: 2,
            });
            const line = new THREE.Line(edgeGeo, edgeMat);
            activeOrganismGroup.add(line);
          });
        }

        // 3. Tierra Parasitism Visualization: Draw ethereal symbiotic/parasitic filament
        if (isParasite && hostCenter && orgIdx > 0) {
          const tetherPoints = [offset.clone(), hostCenter.clone()];
          const tetherGeo = new THREE.BufferGeometry().setFromPoints(tetherPoints);
          const tetherMat = new THREE.LineDashedMaterial({
            color: 0xef476f,
            dashSize: 1.5,
            gapSize: 1.0,
            transparent: true,
            opacity: 0.55,
          });
          const tetherLine = new THREE.Line(tetherGeo, tetherMat);
          tetherLine.computeLineDistances();
          activeOrganismGroup.add(tetherLine);
        }
      });

      // Auto-fit camera so all organisms are always visible
      needsFit = true;           // let the anim loop lerp into place
      _fitCameraStep(1.0);       // also snap immediately so first frame is correct
    }

    // Single lerp step toward the ideal camera position.
    // alpha=1 snaps instantly; default 0.08 smoothly converges over ~30 frames.
    // Returns true when the camera is close enough (converged).
    function _fitCameraStep(alpha = 0.08) {
      if (activeOrganismGroup.children.length === 0) return true;

      const box = new THREE.Box3();
      activeOrganismGroup.traverse((obj) => {
        if (obj.isMesh) box.expandByObject(obj);
      });
      if (box.isEmpty()) return true;

      const sphere = new THREE.Sphere();
      box.getBoundingSphere(sphere);

      const fovRad = THREE.MathUtils.degToRad(camera.fov);
      const fitDist = (sphere.radius / Math.sin(fovRad / 2)) * 1.4;

      const clampedDist = Math.min(
        Math.max(fitDist, controls.minDistance),
        controls.maxDistance
      );

      // Keep the current view direction
      const dir = camera.position.clone().sub(controls.target);
      if (dir.lengthSq() < 0.001) dir.set(0, 0.5, 1);
      dir.normalize();

      const targetPos = sphere.center.clone().add(dir.multiplyScalar(clampedDist));
      const targetLook = sphere.center.clone();

      camera.position.lerp(targetPos, alpha);
      controls.target.lerp(targetLook, alpha);
      controls.update();

      // Converged when within 2% of target distance
      return camera.position.distanceTo(targetPos) < clampedDist * 0.02;
    }

    // Public wrapper kept for backward compat (no longer used for lerp logic)
    function fitCameraToOrganisms() {
      needsFit = true;
      _fitCameraStep(1.0);
    }

    // Switch Environment Atmosphere & Habitat Visuals
    function switchHabitatAtmosphere(speciesKey) {
      const conf = HABITAT_CONFIGS[speciesKey];
      if (!conf) return;

      // Reset organism selection to primary host on world switch
      selectedOrganismId = null;

      // Update CSS Variables for color theme
      document.documentElement.style.setProperty("--active-species-color", conf.color);

      // Update Header & Badge
      document.getElementById("bar-species-name").textContent = conf.name;
      document.getElementById("bar-telos").textContent = conf.telos;
      document.getElementById("canvas-habitat-badge").textContent = conf.titleBadge;

      // Update 3D Lighting and Fog
      scene.fog.color.setHex(conf.fogColor);
      mainPointLight.color.setHex(conf.color);
      particleMat.color.setHex(conf.particleColor);

      // Update 3D Grid
      scene.remove(gridHelper);
      const newGrid = new THREE.GridHelper(80, 20, new THREE.Color(conf.color), new THREE.Color(conf.gridColor));
      newGrid.position.y = -22;
      scene.add(newGrid);

      // Camera re-center: reset to default then let fitCameraToOrganisms() adjust
      camera.position.set(0, 30, 75);
      controls.target.set(0, 0, 0);
      controls.update();

      // Update Dots UI
      const dots = document.querySelectorAll(".slider-dot");
      dots.forEach((dot, idx) => {
        if (idx === currentHabitatIndex) {
          dot.classList.add("active");
        } else {
          dot.classList.remove("active");
        }
      });

      // Update Tabs UI
      const tabs = document.querySelectorAll(".habitat-tab-btn");
      tabs.forEach((tab, idx) => {
        if (idx === currentHabitatIndex) {
          tab.classList.add("active");
        } else {
          tab.classList.remove("active");
        }
      });

      // Render 3D Model & Spotlight Card
      renderActiveOrganismMorphology();
      updateSpotlightCard();
    }

    // Navigation Controls: strictly habitat selection only
    function nextHabitat() {
      currentHabitatIndex = (currentHabitatIndex + 1) % SPECIES_ORDER.length;
      switchHabitatAtmosphere(SPECIES_ORDER[currentHabitatIndex]);
    }

    function prevHabitat() {
      currentHabitatIndex = (currentHabitatIndex - 1 + SPECIES_ORDER.length) % SPECIES_ORDER.length;
      switchHabitatAtmosphere(SPECIES_ORDER[currentHabitatIndex]);
    }

    function selectHabitat(index) {
      currentHabitatIndex = index;
      switchHabitatAtmosphere(SPECIES_ORDER[currentHabitatIndex]);
    }

    // Update the Spotlight Bio-Card with Colony Selector and Tierra Genome Lineage
    function updateSpotlightCard() {
      const activeSpecies = SPECIES_ORDER[currentHabitatIndex];
      const colony = getActiveColony();
      const org = getSelectedOrganism();
      const conf = HABITAT_CONFIGS[activeSpecies];
      if (!org || !conf) return;

      const lineageClass = (org.lineage || "").toLowerCase().includes("parasite")
        ? "lineage-parasite"
        : (org.lineage || "").toLowerCase().includes("hyper")
        ? "lineage-hyper"
        : (org.lineage || "").toLowerCase().includes("mutant")
        ? "lineage-mutant"
        : "lineage-ancestor";

      const card = document.getElementById("spotlight-card");
      const vm = org.tierra_vm;

      // Build Colony Organisms Selector Chips
      let colonyChipsHtml = "";
      if (colony.length > 1) {
        colonyChipsHtml = `
          <div class="colony-selector">
            <span style="font-size: 0.68rem; color: var(--text-dim); margin-right: 0.2rem;">COLONY (${colony.length}):</span>
            ${colony.map(o => {
              const chipActive = o.id === org.id ? "active" : "";
              const tagClass = (o.lineage || "").toLowerCase().includes("parasite")
                ? "lineage-parasite"
                : (o.lineage || "").toLowerCase().includes("hyper")
                ? "lineage-hyper"
                : (o.lineage || "").toLowerCase().includes("mutant")
                ? "lineage-mutant"
                : "lineage-ancestor";
              return `
                <button type="button" class="colony-chip ${chipActive}" data-org-id="${esc(o.id)}" title="${esc(o.name)}">
                  <span class="chip-name">${esc(o.name)}</span>
                  <span class="lineage-tag ${tagClass}">Gen ${num(o.generation)}</span>
                  <span class="chip-born">${esc(formatBirth(o.born_at).relative)}</span>
                </button>
              `;
            }).join("")}
          </div>
        `;
      }
      const birth = formatBirth(org.born_at);

      card.innerHTML = `
        ${colonyChipsHtml}
        <div class="spotlight-header">
          <div>
            <div style="display: flex; align-items: center; gap: 0.55rem;">
              <span class="spotlight-title">${esc(org.name)}</span>
              <span class="lineage-tag ${lineageClass}">${esc(org.lineage || "Ancestor")}</span>
              <span class="lineage-tag" style="background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.15);">Gen ${num(org.generation)}</span>
            </div>
            <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 3px;">${conf.description}</div>
          </div>
          <div class="spotlight-phase">${esc(org.phase)}</div>
        </div>

        <div class="vital-bar-container">
          <div class="vital-bar-label">
            <span>Somatic Energy</span>
            <span>${num(org.energy)}%</span>
          </div>
          <div class="vital-bar-track">
            <div class="vital-bar-fill" style="width: ${num(org.energy)}%;"></div>
          </div>
        </div>

        <div class="vital-bar-container">
          <div class="vital-bar-label">
            <span>${esc(org.special_metric_name)}</span>
            <span>${num(org.growth_score)}</span>
          </div>
          <div class="vital-bar-track">
            <div class="vital-bar-fill" style="width: ${Math.min(100, num(org.growth_score))}%; background: #fff;"></div>
          </div>
        </div>

        <div class="spotlight-birth">
          Born <strong>${esc(birth.absolute)}</strong>${birth.relative ? ` <span>(${esc(birth.relative)})</span>` : ""}
        </div>

        <div class="spotlight-meta-grid">
          <div>Multicellular Nodes: <strong>${num(org.cells_count)} cells</strong></div>
          <div>Lineage Strain: <strong>${esc(org.lineage || "Ancestor-80")}</strong></div>
          <div>Genome Size: <strong>${vm ? (num(vm.genome_size) || 80) : 80} ops</strong></div>
          <div>RAM Soup Locus: <strong>0x${(vm && vm.start_address !== undefined ? num(vm.start_address) : 64).toString(16).toUpperCase()}</strong></div>
          <div>Tierra CPU Cycles: <strong>${vm ? num(vm.total_cycles) : 0} cycles</strong></div>
          <div>Borrowed Host Cycles: <strong>${vm ? num(vm.borrowed_host_cycles) : 0} cycles</strong></div>
          <div>Genome Bit-Flips: <strong>${num(org.mutations_count)} mutations</strong></div>
          <div>Reaper Penalty: <strong>${vm ? num(vm.error_count) : 0} errors</strong></div>
          <div>Tierra VM Divides: <strong>${vm ? num(vm.divide_count) : 0} events</strong></div>
          <div>Parent Strain: <strong>${org.parent_id ? esc(String(org.parent_id).slice(-8)) : "None (Genesis)"}</strong></div>
          <div>Tierra Registers: <strong>IP:${vm ? num(vm.ip) : 0} | AX:${vm && vm.registers ? num(vm.registers.AX) : 0} BX:${vm && vm.registers ? num(vm.registers.BX) : 0}</strong></div>
          <div>Addressing Mode: <strong>Complementary (NOP_0/1)</strong></div>
        </div>
      `;

      const activeChip = card.querySelector(".colony-chip.active");
      if (activeChip) {
        const strip = activeChip.parentElement;
        strip.scrollLeft = activeChip.offsetLeft - (strip.clientWidth - activeChip.offsetWidth) / 2;
      }
    }

    // --- UI Update & Polling (100M Concurrent Users Protected) ---
    let isFetchingVitals = false;
    let vitalsPollTimeout = null;

    // Past growth trials, preserved as static read-only snapshots (same shape as a live /api/v1/vitals response).
    const ARCHIVES = [
      { id: "trial-01", label: "Trial #1 — 2026-09-27 (pre-reset)" },
    ];
    let viewSource = "live";

    async function loadJson(url) {
      const res = await fetch(url, { cache: "default", headers: { "Accept": "application/json" } });
      if (!res.ok) throw new Error(`${url} -> ${res.status}`);
      return res.json();
    }

    function toggleArchiveMenu(force) {
      const dropdown = document.getElementById("archive-dropdown");
      const open = force !== undefined ? force : dropdown.hidden;
      dropdown.hidden = !open;
      document.getElementById("archive-toggle").setAttribute("aria-expanded", String(open));
    }
    function closeArchiveMenu() { toggleArchiveMenu(false); }

    async function loadArchive(id) {
      if (isFetchingVitals) return;
      isFetchingVitals = true;
      try {
        const data = await loadJson(`/archive/${id}.json`);
        organismsData = data.organisms;
        updateUI(data);
        renderActiveOrganismMorphology();
        updateSpotlightCard();
      } catch (e) {
        console.error("Failed to load archive", id, e);
      } finally {
        isFetchingVitals = false;
      }
    }

    function setViewSource(id) {
      viewSource = id;
      closeArchiveMenu();
      document.querySelectorAll(".archive-item").forEach(el => el.classList.toggle("active", el.dataset.view === id));
      document.body.classList.toggle("archive-mode", id !== "live");
      const archive = ARCHIVES.find(a => a.id === id);
      document.getElementById("deck-mode-label").textContent = archive
        ? `ARCHIVE: ${archive.label} (READ-ONLY)`
        : "AUTONOMOUS ECOSYSTEM (ZERO-INPUT OBSERVATION)";

      if (vitalsPollTimeout) { clearTimeout(vitalsPollTimeout); vitalsPollTimeout = null; }
      selectedOrganismId = null;
      if (id === "live") {
        fetchVitals();
        scheduleNextVitalsPoll();
      } else {
        loadArchive(id);
      }
    }

    async function fetchVitals() {
      if (viewSource !== "live" || isFetchingVitals) return;
      isFetchingVitals = true;
      try {
        let data;
        try {
          data = await loadJson("/api/v1/vitals");
        } catch (liveError) {
          // Live endpoint is capped by the free-tier daily quota; fall back to the static snapshot.
          console.warn("Live vitals unavailable, using static snapshot", liveError);
          data = await loadJson("/vitals-snapshot.json");
        }
        organismsData = data.organisms;
        updateUI(data);
        renderActiveOrganismMorphology(); // fitCameraToOrganisms() called inside
        updateSpotlightCard();
      } catch (e) {
        console.error("Failed to fetch vitals", e);
      } finally {
        isFetchingVitals = false;
      }
    }

    function updateUI(data) {
      // Badge
      const badge = document.getElementById("badge-jev");
      badge.textContent = data.jev_connected ? "Jev System One: Online" : "Jev System One: Spatial Heuristic";
      badge.style.color = data.jev_connected ? "var(--gaia-emerald)" : "var(--theos-gold)";

      const ecoBadge = document.getElementById("badge-tierra");
      if (ecoBadge && data.tierra_ecosystem) {
        const eco = data.tierra_ecosystem;
        ecoBadge.textContent = `Tierra 1990 // Shannon H=${eco.diversity_index} | Parasites: ${eco.parasite_count}`;
      }

      // Render Bottom Tabs
      const tabs = document.getElementById("habitat-tabs");
      tabs.innerHTML = "";
      SPECIES_ORDER.forEach((sp, idx) => {
        const colony = data.organisms.filter(o => o.species === sp && o.is_alive !== false);
        const host = colony[0] || data.organisms.find(o => o.species === sp);
        const conf = HABITAT_CONFIGS[sp];
        if (!host || !conf) return;

        const totalCellsNum = colony.reduce((sum, o) => sum + num(o.cells_count), 0);
        const orgsLabel = colony.length > 1 ? `${colony.length} orgs (${totalCellsNum}c)` : `${num(host.cells_count)} cells // ${num(host.energy)}%`;

        const btn = document.createElement("div");
        btn.className = `habitat-tab-btn ${idx === currentHabitatIndex ? "active" : ""}`;
        btn.style.setProperty("--tab-color", conf.color);
        btn.dataset.habitat = String(idx);
        btn.innerHTML = `
          <div class="tab-species-name">${conf.name.split(" ")[0]}</div>
          <div class="tab-cells-count">${orgsLabel}</div>
        `;
        tabs.appendChild(btn);

        colony.forEach(o => {
          if (o.last_thought) {
            addPulseLog(o.name, conf.color, o.last_thought);
          }
        });
      });

      // Crystals
      document.getElementById("crystal-count").textContent = `${data.recent_crystals.length} crystals`;
      const crystalsFeed = document.getElementById("crystals-feed");
      crystalsFeed.innerHTML = "";
      data.recent_crystals.forEach(c => {
        const chip = document.createElement("div");
        chip.className = "crystal-chip";
        chip.innerHTML = `
          <div class="crystal-title">[${esc(String(c.species ?? "").toUpperCase())}] ${esc(c.concept_title)}</div>
          <div class="crystal-insight">${esc(c.core_insight)}</div>
        `;
        crystalsFeed.appendChild(chip);
      });
    }

    const seenPulseKeys = new Set();
    function addPulseLog(organismName, color, thought) {
      const key = `${thought.pulse_index}-${thought.timestamp}`;
      if (seenPulseKeys.has(key)) return;
      seenPulseKeys.add(key);

      const stream = document.getElementById("pulse-stream");
      const item = document.createElement("div");
      item.className = "pulse-item";
      const thoughtTime = new Date(thought.timestamp);
      const timeStr = Number.isNaN(thoughtTime.getTime()) ? "--:--:--" : formatClock(thoughtTime);
      item.innerHTML = `
        <span style="color: var(--text-dim);">[${esc(timeStr)}]</span>
        <span class="pulse-tag" style="color: ${color};">${esc(organismName)}</span>
        <span>Choice: <strong>${esc(thought.action_chosen)}</strong></span>
        <div style="color: #cbd5e1; font-size: 0.72rem; margin-top: 2px;">↳ ${esc(thought.rationale)}</div>
      `;
      stream.prepend(item);
      if (stream.children.length > 60) {
        stream.removeChild(stream.lastChild);
      }
    }

    // Snapshots only change once per heartbeat, and every live request spends free-tier quota.
    function scheduleNextVitalsPoll() {
      if (vitalsPollTimeout) clearTimeout(vitalsPollTimeout);
      if (document.hidden || viewSource !== "live") return; // Idle in background, or while viewing an archive
      const jitterMs = Math.floor(Math.random() * 60000);
      vitalsPollTimeout = setTimeout(async () => {
        await fetchVitals();
        scheduleNextVitalsPoll();
      }, 120000 + jitterMs);
    }

    document.addEventListener("visibilitychange", () => {
      if (viewSource !== "live") return; // An archive stays put; it never refreshes from live data
      if (!document.hidden) {
        fetchVitals();
        scheduleNextVitalsPoll();
      } else if (vitalsPollTimeout) {
        clearTimeout(vitalsPollTimeout);
      }
    });

    // Sponsored text links: plain anchors only (no ad scripts or tracking pixels), rendered from sponsors.json.
    async function loadSponsors() {
      try {
        const sponsors = await loadJson("/sponsors.json");
        const valid = (Array.isArray(sponsors) ? sponsors : []).filter(s => {
          try { return s && s.label && ["https:", "http:"].includes(new URL(s.url).protocol); } catch { return false; }
        });
        if (valid.length === 0) return;
        document.getElementById("signal-relay-list").innerHTML = valid.map(s => `
          <li>
            <a href="${esc(s.url)}" target="_blank" rel="sponsored noopener noreferrer">${esc(s.label)}</a>
            ${s.note ? `<span class="signal-relay-note">${esc(s.note)}</span>` : ""}
          </li>
        `).join("");
        document.getElementById("signal-relay").hidden = false;
      } catch (e) {
        console.warn("Sponsors unavailable", e);
      }
    }

    // Initial fetch & start jittered polling
    fetchVitals();
    scheduleNextVitalsPoll();
    loadSponsors();
