export interface Option {
  value: string
  label: string
}

export interface SearchFilters {
  states: string[]
  categories: string[]
  ageRange: string
  genders: string[]
  castes: string[]
  areas: string[]
  disability: string
  profession: string
}

export const SCHEME_CATEGORY_OPTIONS: Option[] = [
  { value: "social_welfare_empowerment", label: "Social Welfare & Empowerment" },
  { value: "education_learning", label: "Education & Learning" },
  { value: "agriculture_rural_environment", label: "Agriculture, Rural & Environment" },
  { value: "business_entrepreneurship", label: "Business & Entrepreneurship" },
  { value: "women_child", label: "Women and Child" },
  { value: "skills_employment", label: "Skills & Employment" },
  { value: "banking_financial_services_insurance", label: "Banking, Financial Services and Insurance" },
  { value: "health_wellness", label: "Health & Wellness" },
  { value: "sports_culture", label: "Sports & Culture" },
  { value: "housing_shelter", label: "Housing & Shelter" },
  { value: "science_it_communications", label: "Science, IT & Communications" },
  { value: "transport_infrastructure", label: "Transport & Infrastructure" },
  { value: "travel_tourism", label: "Travel & Tourism" },
  { value: "utility_sanitation", label: "Utility & Sanitation" },
  { value: "public_safety_law_justice", label: "Public Safety, Law & Justice" },
]

export const SEARCH_STATE_OPTIONS: Option[] = [
  { value: "Central", label: "Central" },
  { value: "Andaman and Nicobar Islands", label: "Andaman and Nicobar Islands" },
  { value: "Andhra Pradesh", label: "Andhra Pradesh" },
  { value: "Arunachal Pradesh", label: "Arunachal Pradesh" },
  { value: "Assam", label: "Assam" },
  { value: "Bihar", label: "Bihar" },
  { value: "Chandigarh", label: "Chandigarh" },
  { value: "Chhattisgarh", label: "Chhattisgarh" },
  { value: "Dadra and Nagar Haveli and Daman and Diu", label: "Dadra and Nagar Haveli and Daman and Diu" },
  { value: "Delhi", label: "Delhi" },
  { value: "Goa", label: "Goa" },
  { value: "Gujarat", label: "Gujarat" },
  { value: "Haryana", label: "Haryana" },
  { value: "Himachal Pradesh", label: "Himachal Pradesh" },
  { value: "Jammu and Kashmir", label: "Jammu and Kashmir" },
  { value: "Jharkhand", label: "Jharkhand" },
  { value: "Karnataka", label: "Karnataka" },
  { value: "Kerala", label: "Kerala" },
  { value: "Ladakh", label: "Ladakh" },
  { value: "Lakshadweep", label: "Lakshadweep" },
  { value: "Madhya Pradesh", label: "Madhya Pradesh" },
  { value: "Maharashtra", label: "Maharashtra" },
  { value: "Manipur", label: "Manipur" },
  { value: "Meghalaya", label: "Meghalaya" },
  { value: "Mizoram", label: "Mizoram" },
  { value: "Nagaland", label: "Nagaland" },
  { value: "Odisha", label: "Odisha" },
  { value: "Puducherry", label: "Puducherry" },
  { value: "Punjab", label: "Punjab" },
  { value: "Rajasthan", label: "Rajasthan" },
  { value: "Sikkim", label: "Sikkim" },
  { value: "Tamil Nadu", label: "Tamil Nadu" },
  { value: "Telangana", label: "Telangana" },
  { value: "Tripura", label: "Tripura" },
  { value: "Uttar Pradesh", label: "Uttar Pradesh" },
  { value: "Uttarakhand", label: "Uttarakhand" },
  { value: "West Bengal", label: "West Bengal" },
]

export const PROFILE_STATE_OPTIONS = SEARCH_STATE_OPTIONS.filter(
  (option) => option.value !== "Central",
)

export const GENDER_OPTIONS: Option[] = [
  { value: "Male", label: "Male" },
  { value: "Female", label: "Female" },
  { value: "Transgender", label: "Transgender" },
]

export const CASTE_OPTIONS: Option[] = [
  { value: "General", label: "General" },
  { value: "OBC", label: "OBC" },
  { value: "SC", label: "SC" },
  { value: "ST", label: "ST" },
  { value: "EWS", label: "EWS" },
  { value: "Minority", label: "Minority" },
]

export const AREA_OPTIONS: Option[] = [
  { value: "Urban", label: "Urban" },
  { value: "Rural", label: "Rural" },
]

export const DISABILITY_OPTIONS: Option[] = [
  { value: "No", label: "No" },
  { value: "Yes", label: "Yes" },
]

export const PROFESSION_OPTIONS: Option[] = [
  { value: "Student", label: "Student" },
  { value: "Farmer", label: "Farmer" },
  { value: "Entrepreneur / Self-Employed", label: "Entrepreneur / Self-Employed" },
  { value: "Corporate Employee", label: "Corporate Employee" },
  { value: "Government Employee", label: "Government Employee" },
  { value: "Unemployed", label: "Unemployed" },
  { value: "Other", label: "Other" },
]

export const AGE_RANGE_OPTIONS: Option[] = [
  { value: "0-10", label: "0-10" },
  { value: "11-20", label: "11-20" },
  { value: "21-30", label: "21-30" },
  { value: "31-40", label: "31-40" },
  { value: "41-50", label: "41-50" },
  { value: "51-60", label: "51-60" },
  { value: "61-70", label: "61-70" },
  { value: "71-80", label: "71-80" },
  { value: "81+", label: "81+" },
]

export function createEmptySearchFilters(): SearchFilters {
  return {
    states: [],
    categories: [],
    ageRange: "",
    genders: [],
    castes: [],
    areas: [],
    disability: "",
    profession: "",
  }
}

export function countActiveSearchFilters(filters: SearchFilters): number {
  return (
    filters.states.length +
    filters.categories.length +
    filters.genders.length +
    filters.castes.length +
    filters.areas.length +
    (filters.ageRange ? 1 : 0) +
    (filters.disability ? 1 : 0) +
    (filters.profession ? 1 : 0)
  )
}

export function toggleFilterValue(values: string[], nextValue: string): string[] {
  return values.includes(nextValue)
    ? values.filter((value) => value !== nextValue)
    : [...values, nextValue]
}
