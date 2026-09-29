import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type {
  Reconstruction3DOutput,
  ReconstructionDefect,
} from '../types/digitalTwin';
import { RotateCcw, Eye } from 'lucide-react';

interface ThreeDPipeViewerProps {
  reconstruction: Reconstruction3DOutput | null;
  selectedDefectId?: string | null;
  onSelectDefect?: (defect: ReconstructionDefect) => void;
  isWireframe?: boolean;
}

export default function ThreeDPipeViewer({
  reconstruction,
  selectedDefectId,
  onSelectDefect,
  isWireframe = false,
}: ThreeDPipeViewerProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [webglError, setWebglError] = useState<boolean>(false);
  const [showDefects, setShowDefects] = useState<boolean>(true);


  // References for WebGL cleanup & controls
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const defectsGroupRef = useRef<THREE.Group | null>(null);
  const pipeMeshRef = useRef<THREE.Mesh | null>(null);

  // Control state refs for smooth orbit/drag
  const isDraggingRef = useRef<boolean>(false);
  const previousMouseRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const rotationRef = useRef<{ x: number; y: number }>({ x: 0.2, y: -0.6 });

  // WebGL 3D Scene Initialization
  useEffect(() => {
    const container = mountRef.current;
    if (!container || !reconstruction) return;

    try {
      const width = container.clientWidth || 600;
      const height = container.clientHeight || 380;

      // 1. Scene Setup
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x050e0f);
      sceneRef.current = scene;

      // 2. Camera Setup
      const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
      const pipeLength = reconstruction.total_length_m || 50;
      camera.position.set(0, 4, 18);
      camera.lookAt(0, 0, 0);
      cameraRef.current = camera;

      // 3. WebGL Renderer Setup
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      rendererRef.current = renderer;

      // Clear container and append canvas
      container.innerHTML = '';
      container.appendChild(renderer.domElement);

      // 4. Lighting
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
      scene.add(ambientLight);

      const dirLight1 = new THREE.DirectionalLight(0x5de6ff, 1.2);
      dirLight1.position.set(20, 40, 30);
      scene.add(dirLight1);

      const dirLight2 = new THREE.DirectionalLight(0xa3e635, 0.8);
      dirLight2.position.set(-20, -20, -30);
      scene.add(dirLight2);

      // 5. Main Pipe Mesh Construction
      const pipeGroup = new THREE.Group();
      scene.add(pipeGroup);

      const radius = (reconstruction.diameter_mm / 2000) || 0.3; // Convert mm to meters radius
      const geom = new THREE.CylinderGeometry(radius, radius, pipeLength, 32, 32, true);
      // Rotate cylinder horizontally along Z axis
      geom.rotateX(Math.PI / 2);

      const mat = new THREE.MeshStandardMaterial({
        color: 0x143c3e,
        roughness: 0.4,
        metalness: 0.3,
        side: THREE.DoubleSide,
        wireframe: isWireframe,
        transparent: true,
        opacity: 0.85,
      });

      const pipeMesh = new THREE.Mesh(geom, mat);
      pipeMeshRef.current = pipeMesh;
      pipeGroup.add(pipeMesh);

      // 6. Section Rings & Centerline
      const sectionCount = reconstruction.section_count || 10;
      const secLength = pipeLength / sectionCount;

      for (let i = 0; i <= sectionCount; i++) {
        const zPos = -pipeLength / 2 + i * secLength;
        const ringGeom = new THREE.TorusGeometry(radius * 1.01, 0.015, 16, 32);
        const ringMat = new THREE.MeshBasicMaterial({
          color: i * secLength <= reconstruction.reconstructed_length_m ? 0x5de6ff : 0x1e4848,
          wireframe: false,
        });
        const ringMesh = new THREE.Mesh(ringGeom, ringMat);
        ringMesh.position.set(0, 0, zPos);
        pipeGroup.add(ringMesh);
      }

      // Progress boundary ring (Lime accent)
      const progressZ = -pipeLength / 2 + (reconstruction.reconstructed_length_m || 0);
      const progRingGeom = new THREE.TorusGeometry(radius * 1.02, 0.03, 16, 32);
      const progRingMat = new THREE.MeshBasicMaterial({ color: 0xa3e635 });
      const progRingMesh = new THREE.Mesh(progRingGeom, progRingMat);
      progRingMesh.position.set(0, 0, progressZ);
      pipeGroup.add(progRingMesh);

      // Centerline path
      const points = [
        new THREE.Vector3(0, 0, -pipeLength / 2),
        new THREE.Vector3(0, 0, pipeLength / 2),
      ];
      const lineGeom = new THREE.BufferGeometry().setFromPoints(points);
      const lineMat = new THREE.LineDashedMaterial({
        color: 0xa3e635,
        dashSize: 0.5,
        gapSize: 0.25,
      });
      const centerline = new THREE.Line(lineGeom, lineMat);
      centerline.computeLineDistances();
      pipeGroup.add(centerline);

      // 7. Defect Markers Group
      const defectsGroup = new THREE.Group();
      pipeGroup.add(defectsGroup);
      defectsGroupRef.current = defectsGroup;

      if (showDefects && reconstruction.defects) {
        reconstruction.defects.forEach((def) => {
          const zPos = -pipeLength / 2 + Math.min(def.distance_m, pipeLength);
          const angleRad = (def.clock_angle_deg * Math.PI) / 180;
          const rMarker = radius * 0.96;
          const xPos = rMarker * Math.sin(angleRad);
          const yPos = rMarker * Math.cos(angleRad);

          const isSelected = selectedDefectId === def.id;
          const markerSize = isSelected ? 0.28 : 0.18;
          const sphereGeom = new THREE.SphereGeometry(markerSize, 16, 16);

          const isHighSev = def.severity === 'CRITICAL' || def.severity === 'HIGH';
          const colorHex = isHighSev ? 0xff5449 : 0xffb4ab;

          const sphereMat = new THREE.MeshStandardMaterial({
            color: colorHex,
            emissive: isSelected ? 0xff5449 : 0x000000,
            roughness: 0.2,
            metalness: 0.8,
          });

          const sphereMesh = new THREE.Mesh(sphereGeom, sphereMat);
          sphereMesh.position.set(xPos, yPos, zPos);
          sphereMesh.userData = { defect: def };
          defectsGroup.add(sphereMesh);
        });
      }

      // 8. Mouse Interactive Orbit Control
      const handleMouseDown = (e: MouseEvent) => {
        isDraggingRef.current = true;
        previousMouseRef.current = { x: e.clientX, y: e.clientY };
      };

      const handleMouseMove = (e: MouseEvent) => {
        if (!isDraggingRef.current) return;
        const deltaX = e.clientX - previousMouseRef.current.x;
        const deltaY = e.clientY - previousMouseRef.current.y;

        rotationRef.current.y += deltaX * 0.008;
        rotationRef.current.x += deltaY * 0.008;
        // Clamp X rotation to prevent flipping
        rotationRef.current.x = Math.max(-Math.PI / 3, Math.min(Math.PI / 3, rotationRef.current.x));

        previousMouseRef.current = { x: e.clientX, y: e.clientY };
      };

      const handleMouseUp = () => {
        isDraggingRef.current = false;
      };

      const handleWheel = (e: WheelEvent) => {
        e.preventDefault();
        if (!cameraRef.current) return;
        cameraRef.current.position.z += e.deltaY * 0.05;
        cameraRef.current.position.z = Math.max(10, Math.min(pipeLength * 1.5, cameraRef.current.position.z));
      };

      // Raycaster for defect selection
      const raycaster = new THREE.Raycaster();
      const mouse = new THREE.Vector2();

      const handleClick = (e: MouseEvent) => {
        const rect = renderer.domElement.getBoundingClientRect();
        mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);
        const intersects = raycaster.intersectObjects(defectsGroup.children);

        if (intersects.length > 0) {
          const clickedMesh = intersects[0].object;
          const clickedDefect = clickedMesh.userData.defect as ReconstructionDefect;
          if (clickedDefect && onSelectDefect) {
            onSelectDefect(clickedDefect);
          }
        }
      };

      const domElem = renderer.domElement;
      domElem.addEventListener('mousedown', handleMouseDown);
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      domElem.addEventListener('wheel', handleWheel, { passive: false });
      domElem.addEventListener('click', handleClick);

      // 9. Animation Render Loop
      const animate = () => {
        animFrameRef.current = requestAnimationFrame(animate);

        pipeGroup.rotation.x = rotationRef.current.x;
        pipeGroup.rotation.y = rotationRef.current.y;

        renderer.render(scene, camera);
      };

      animate();

      // Handle Window Resize
      const handleResize = () => {
        if (!container || !rendererRef.current || !cameraRef.current) return;
        const w = container.clientWidth;
        const h = container.clientHeight;
        cameraRef.current.aspect = w / h;
        cameraRef.current.updateProjectionMatrix();
        rendererRef.current.setSize(w, h);
      };

      window.addEventListener('resize', handleResize);

      return () => {
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        domElem.removeEventListener('mousedown', handleMouseDown);
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        domElem.removeEventListener('wheel', handleWheel);
        domElem.removeEventListener('click', handleClick);
        window.removeEventListener('resize', handleResize);
        renderer.dispose();
      };
    } catch (err) {
      console.warn('WebGL 3D Context initialization failed, falling back to 2D viewer mode:', err);
      setWebglError(true);
    }
  }, [reconstruction, isWireframe, showDefects, selectedDefectId]);

  const resetView = () => {
    rotationRef.current = { x: 0.2, y: -0.6 };
    if (cameraRef.current) {
      cameraRef.current.position.set(0, 4, 18);
      cameraRef.current.lookAt(0, 0, 0);
    }
  };

  // If WebGL failed or is unavailable, render clean 2D vector fallback
  if (webglError) {
    return (
      <div className="w-full h-full bg-[#050e0f] rounded-lg border border-[#173838] relative flex flex-col items-center justify-center p-6 text-center">
        <div className="absolute top-4 left-4 bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[10px] font-['Space_Mono'] font-bold uppercase px-2.5 py-1 rounded">
          2D Vector Fallback Mode
        </div>

        <svg className="w-full h-[300px]" viewBox="0 0 600 240">
          <rect x="50" y="60" width="500" height="120" rx="12" fill="#0c2324" stroke="#19484a" strokeWidth="2" />
          <line x1="50" y1="120" x2="550" y2="120" stroke="#a3e635" strokeDasharray="4 2" />

          {reconstruction?.defects?.map((def) => {
            const ratio = Math.min(def.distance_m / (reconstruction.total_length_m || 50), 1.0);
            const xPos = 50 + ratio * 500;
            const isSelected = selectedDefectId === def.id;
            return (
              <circle
                key={def.id}
                cx={xPos}
                cy={120}
                r={isSelected ? 8 : 5}
                fill="#ff5449"
                onClick={() => onSelectDefect && onSelectDefect(def)}
                className="cursor-pointer"
              />
            );
          })}
        </svg>
      </div>
    );
  }

  return (
    <div className="w-full h-[380px] bg-[#050e0f] rounded-lg border border-[#173838] relative overflow-hidden flex items-center justify-center">
      {/* WebGL Canvas Container */}
      <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Floating 3D Controls */}
      <div className="absolute bottom-4 left-4 bg-[#0a1617]/90 border border-[#1e4848] p-1.5 rounded-lg flex items-center gap-2 z-20">
        <button
          onClick={resetView}
          title="Reset Camera View"
          className="p-1.5 text-[#649c96] hover:text-white hover:bg-white/10 rounded transition-all cursor-pointer"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={() => setShowDefects(!showDefects)}
          title="Toggle Defect Markers"
          className={`p-1.5 rounded transition-all cursor-pointer ${
            showDefects ? 'text-[#a3e635] bg-[#a3e635]/10' : 'text-[#649c96] hover:text-white'
          }`}
        >
          <Eye className="w-3.5 h-3.5" />
        </button>

        <span className="text-[10px] font-['Space_Mono'] text-[#649c96] px-1 border-l border-[#1e4848]">
          Orbit: Drag • Zoom: Scroll
        </span>
      </div>
    </div>
  );
}
