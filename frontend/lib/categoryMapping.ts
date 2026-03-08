/**
 * Maps 50 backend SWE categories → 8 frontend brain regions
 * 
 * Backend categories (from profile_scoring/categories.py):
 *   Fundamentals, OOP, Data Structures, Algorithms, Systems, Dev Practices
 * 
 * Frontend regions (from brain_regions.json):
 *   Region_Frontend, Region_Backend, Region_AI, Region_Data,
 *   Region_Systems, Region_DevOps, Region_Product, Region_Hackathon
 */

// All 50 backend category keys
export const BACKEND_CATEGORIES = [
  // Fundamentals
  'variables', 'functions', 'control_flow', 'recursion',
  // OOP
  'oop', 'classes', 'objects', 'inheritance', 'polymorphism',
  'encapsulation', 'abstraction', 'methods', 'constructors',
  // Data Structures
  'data_structures', 'arrays', 'linked_lists', 'stacks', 'queues',
  'trees', 'graphs', 'hash_tables',
  // Algorithms
  'algorithms', 'sorting', 'searching', 'dynamic_programming',
  'time_complexity', 'space_complexity',
  // Systems
  'databases', 'sql', 'indexing', 'apis', 'operating_systems',
  'memory_management', 'concurrency', 'networking',
  // Dev Practices
  'git', 'testing',
] as const

export type BackendCategory = typeof BACKEND_CATEGORIES[number]

// Frontend region IDs (must match brain_regions.json)
export const FRONTEND_REGIONS = [
  'Region_Frontend',
  'Region_Backend', 
  'Region_AI',
  'Region_Data',
  'Region_Systems',
  'Region_DevOps',
  'Region_Product',
  'Region_Hackathon',
] as const

export type FrontendRegion = typeof FRONTEND_REGIONS[number]

// Mapping: backend category → frontend region
export const CATEGORY_TO_REGION: Record<BackendCategory, FrontendRegion> = {
  // Fundamentals → Backend (core programming)
  variables: 'Region_Backend',
  functions: 'Region_Backend',
  control_flow: 'Region_Backend',
  recursion: 'Region_Backend',

  // OOP → Backend
  oop: 'Region_Backend',
  classes: 'Region_Backend',
  objects: 'Region_Backend',
  inheritance: 'Region_Backend',
  polymorphism: 'Region_Backend',
  encapsulation: 'Region_Backend',
  abstraction: 'Region_Backend',
  methods: 'Region_Backend',
  constructors: 'Region_Backend',

  // Data Structures → Data
  data_structures: 'Region_Data',
  arrays: 'Region_Data',
  linked_lists: 'Region_Data',
  stacks: 'Region_Data',
  queues: 'Region_Data',
  trees: 'Region_Data',
  graphs: 'Region_Data',
  hash_tables: 'Region_Data',

  // Algorithms → AI (algorithmic thinking)
  algorithms: 'Region_AI',
  sorting: 'Region_AI',
  searching: 'Region_AI',
  dynamic_programming: 'Region_AI',
  time_complexity: 'Region_AI',
  space_complexity: 'Region_AI',

  // Systems → split between Systems and Data
  databases: 'Region_Data',
  sql: 'Region_Data',
  indexing: 'Region_Data',
  apis: 'Region_Backend',
  operating_systems: 'Region_Systems',
  memory_management: 'Region_Systems',
  concurrency: 'Region_Systems',
  networking: 'Region_Systems',

  // Dev Practices → DevOps
  git: 'Region_DevOps',
  testing: 'Region_DevOps',
}

// Reverse mapping: region → list of categories that map to it
export const REGION_TO_CATEGORIES: Record<FrontendRegion, BackendCategory[]> = 
  FRONTEND_REGIONS.reduce((acc, region) => {
    acc[region] = BACKEND_CATEGORIES.filter(cat => CATEGORY_TO_REGION[cat] === region)
    return acc
  }, {} as Record<FrontendRegion, BackendCategory[]>)

/**
 * Aggregate 50 backend category scores into 8 frontend region scores
 * Uses average of all categories mapped to each region
 */
export function aggregateToRegions(
  categoryScores: Record<string, number>
): Record<FrontendRegion, number> {
  const regionScores = {} as Record<FrontendRegion, number>

  for (const region of FRONTEND_REGIONS) {
    const categories = REGION_TO_CATEGORIES[region]
    if (categories.length === 0) {
      regionScores[region] = 0
      continue
    }

    const sum = categories.reduce((acc, cat) => {
      return acc + (categoryScores[cat] ?? 0)
    }, 0)
    
    regionScores[region] = sum / categories.length
  }

  return regionScores
}

/**
 * Get human-readable label for a region
 */
export function getRegionLabel(regionId: FrontendRegion): string {
  return regionId.replace('Region_', '')
}

/**
 * Get the categories that contribute to a region with their scores
 */
export function getRegionBreakdown(
  regionId: FrontendRegion,
  categoryScores: Record<string, number>
): { category: BackendCategory; score: number; label: string }[] {
  const categories = REGION_TO_CATEGORIES[regionId]
  
  return categories.map(cat => ({
    category: cat,
    score: categoryScores[cat] ?? 0,
    label: cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
  })).sort((a, b) => b.score - a.score)
}
