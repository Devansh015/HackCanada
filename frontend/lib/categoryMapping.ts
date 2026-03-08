/**
 * Maps 50 backend SWE categories → 9 frontend brain regions (1:1 with category groups)
 *
 * Each categories.py group has its own brain region — no dilution.
 *
 * Groups (categories.py):
 *   Fundamentals(4), OOP(9), DataStructures(8), Algorithms(6),
 *   Systems(8), Frontend(5), DevPractices(5), Product(3), Hackathon(3)
 */

// All 50 backend category keys (must match categories.py exactly)
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
  // Frontend
  'html_css', 'javascript_ts', 'react', 'responsive_design', 'ui_ux',
  // Dev Practices
  'git', 'testing', 'ci_cd', 'docker_containers', 'cloud_infra',
  // Product
  'documentation', 'project_management', 'system_design',
  // Hackathon
  'prototyping', 'integrations', 'problem_solving',
] as const

export type BackendCategory = typeof BACKEND_CATEGORIES[number]

// 9 frontend region IDs — one per category group (must match brain_regions.json)
export const FRONTEND_REGIONS = [
  'Region_Fundamentals',
  'Region_OOP',
  'Region_DataStructures',
  'Region_Algorithms',
  'Region_Systems',
  'Region_Frontend',
  'Region_DevPractices',
  'Region_Product',
  'Region_Hackathon',
] as const

export type FrontendRegion = typeof FRONTEND_REGIONS[number]

// Direct 1:1 mapping: each category → its own group's region
export const CATEGORY_TO_REGION: Record<BackendCategory, FrontendRegion> = {
  // Fundamentals
  variables:            'Region_Fundamentals',
  functions:            'Region_Fundamentals',
  control_flow:         'Region_Fundamentals',
  recursion:            'Region_Fundamentals',

  // OOP
  oop:                  'Region_OOP',
  classes:              'Region_OOP',
  objects:              'Region_OOP',
  inheritance:          'Region_OOP',
  polymorphism:         'Region_OOP',
  encapsulation:        'Region_OOP',
  abstraction:          'Region_OOP',
  methods:              'Region_OOP',
  constructors:         'Region_OOP',

  // Data Structures
  data_structures:      'Region_DataStructures',
  arrays:               'Region_DataStructures',
  linked_lists:         'Region_DataStructures',
  stacks:               'Region_DataStructures',
  queues:               'Region_DataStructures',
  trees:                'Region_DataStructures',
  graphs:               'Region_DataStructures',
  hash_tables:          'Region_DataStructures',

  // Algorithms
  algorithms:           'Region_Algorithms',
  sorting:              'Region_Algorithms',
  searching:            'Region_Algorithms',
  dynamic_programming:  'Region_Algorithms',
  time_complexity:      'Region_Algorithms',
  space_complexity:     'Region_Algorithms',

  // Systems
  databases:            'Region_Systems',
  sql:                  'Region_Systems',
  indexing:             'Region_Systems',
  apis:                 'Region_Systems',
  operating_systems:    'Region_Systems',
  memory_management:    'Region_Systems',
  concurrency:          'Region_Systems',
  networking:           'Region_Systems',

  // Frontend
  html_css:             'Region_Frontend',
  javascript_ts:        'Region_Frontend',
  react:                'Region_Frontend',
  responsive_design:    'Region_Frontend',
  ui_ux:                'Region_Frontend',

  // Dev Practices
  git:                  'Region_DevPractices',
  testing:              'Region_DevPractices',
  ci_cd:                'Region_DevPractices',
  docker_containers:    'Region_DevPractices',
  cloud_infra:          'Region_DevPractices',

  // Product
  documentation:        'Region_Product',
  project_management:   'Region_Product',
  system_design:        'Region_Product',

  // Hackathon
  prototyping:          'Region_Hackathon',
  integrations:         'Region_Hackathon',
  problem_solving:      'Region_Hackathon',
}

// Reverse mapping: region → list of categories
export const REGION_TO_CATEGORIES: Record<FrontendRegion, BackendCategory[]> =
  FRONTEND_REGIONS.reduce((acc, region) => {
    acc[region] = BACKEND_CATEGORIES.filter(cat => CATEGORY_TO_REGION[cat] === region)
    return acc
  }, {} as Record<FrontendRegion, BackendCategory[]>)

/**
 * Aggregate 50 backend category scores → 9 region scores.
 * Uses top-3 average per region (avoids dilution in large groups).
 * Regions with no scored categories are omitted (stays dark).
 */
const TOP_N = 3

export function aggregateToRegions(
  categoryScores: Record<string, number>
): Record<FrontendRegion, number> {
  const regionScores = {} as Record<FrontendRegion, number>

  for (const region of FRONTEND_REGIONS) {
    const categories = REGION_TO_CATEGORIES[region]
    // Collect non-zero scores, sorted descending
    const scores = categories
      .map(cat => categoryScores[cat] ?? 0)
      .filter(s => s > 0)
      .sort((a, b) => b - a)

    if (scores.length === 0) continue          // leave key absent → stays dark

    const top = scores.slice(0, 3)
    regionScores[region] = top.reduce((a, b) => a + b, 0) / top.length
  }

  return regionScores
}

/** Human-readable label for a region */
export function getRegionLabel(regionId: FrontendRegion): string {
  const labels: Record<FrontendRegion, string> = {
    Region_Fundamentals:  'Fundamentals',
    Region_OOP:           'OOP',
    Region_DataStructures:'Data Structures',
    Region_Algorithms:    'Algorithms',
    Region_Systems:       'Systems',
    Region_Frontend:      'Frontend',
    Region_DevPractices:  'Dev Practices',
    Region_Product:       'Product',
    Region_Hackathon:     'Hackathon',
  }
  return labels[regionId] ?? regionId.replace('Region_', '')
}

/** Categories that contribute to a region, sorted by score descending */
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
