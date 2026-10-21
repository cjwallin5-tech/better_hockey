// NHL nationality codes (ISO 3166 alpha-3) -> [alpha-2 for the flag image, name].
const COUNTRIES = {
  CAN: ['ca', 'Canada'], USA: ['us', 'United States'], SWE: ['se', 'Sweden'], FIN: ['fi', 'Finland'], RUS: ['ru', 'Russia'],
  CZE: ['cz', 'Czechia'], SVK: ['sk', 'Slovakia'], CHE: ['ch', 'Switzerland'], DEU: ['de', 'Germany'], DNK: ['dk', 'Denmark'],
  NOR: ['no', 'Norway'], LVA: ['lv', 'Latvia'], BLR: ['by', 'Belarus'], AUT: ['at', 'Austria'], FRA: ['fr', 'France'],
  GBR: ['gb', 'United Kingdom'], UKR: ['ua', 'Ukraine'], KAZ: ['kz', 'Kazakhstan'], LTU: ['lt', 'Lithuania'], SVN: ['si', 'Slovenia'],
  POL: ['pl', 'Poland'], ITA: ['it', 'Italy'], NLD: ['nl', 'Netherlands'], AUS: ['au', 'Australia'], JAM: ['jm', 'Jamaica'],
  PRY: ['py', 'Paraguay'], HRV: ['hr', 'Croatia'], VEN: ['ve', 'Venezuela'], SRB: ['rs', 'Serbia'], IRL: ['ie', 'Ireland'],
  NGA: ['ng', 'Nigeria'], BHS: ['bs', 'Bahamas'], KOR: ['kr', 'South Korea'], LBN: ['lb', 'Lebanon'], JPN: ['jp', 'Japan'],
  CHN: ['cn', 'China'], HUN: ['hu', 'Hungary'], EST: ['ee', 'Estonia'], BEL: ['be', 'Belgium'], ESP: ['es', 'Spain'],
  BRA: ['br', 'Brazil'], MEX: ['mx', 'Mexico'], ISR: ['il', 'Israel'], ARG: ['ar', 'Argentina'], BGR: ['bg', 'Bulgaria'],
  ROU: ['ro', 'Romania'], ISL: ['is', 'Iceland'], TUR: ['tr', 'Turkey'], NZL: ['nz', 'New Zealand'], ZAF: ['za', 'South Africa'],
  BMU: ['bm', 'Bermuda'], TTO: ['tt', 'Trinidad and Tobago'], HTI: ['ht', 'Haiti'], CUB: ['cu', 'Cuba'], COL: ['co', 'Colombia'],
  UZB: ['uz', 'Uzbekistan'], MNE: ['me', 'Montenegro'], BIH: ['ba', 'Bosnia and Herzegovina'], MKD: ['mk', 'North Macedonia'],
  GEO: ['ge', 'Georgia'], ARM: ['am', 'Armenia'], AZE: ['az', 'Azerbaijan'], MDA: ['md', 'Moldova'], LUX: ['lu', 'Luxembourg'],
  CYP: ['cy', 'Cyprus'], GRC: ['gr', 'Greece'], PRT: ['pt', 'Portugal'], IND: ['in', 'India'], THA: ['th', 'Thailand'],
  PHL: ['ph', 'Philippines'], SGP: ['sg', 'Singapore'], DOM: ['do', 'Dominican Republic'], PRI: ['pr', 'Puerto Rico'],
  GHA: ['gh', 'Ghana'], SEN: ['sn', 'Senegal'], CIV: ['ci', "Côte d'Ivoire"], ZWE: ['zw', 'Zimbabwe'], KEN: ['ke', 'Kenya'],
  SUR: ['sr', 'Suriname'], GUY: ['gy', 'Guyana'], BRB: ['bb', 'Barbados'], VIR: ['vi', 'U.S. Virgin Islands'],
}

/** {code2, name} for an NHL country code, or null when unknown. */
export function countryInfo(code) {
  const c = COUNTRIES[code]
  return c ? { code2: c[0], name: c[1] } : null
}
