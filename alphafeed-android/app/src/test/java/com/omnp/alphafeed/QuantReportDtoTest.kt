package com.omnp.alphafeed

import com.omnp.alphafeed.data.remote.dto.QuantReportDto
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class QuantReportDtoTest {
    private val json = Json { ignoreUnknownKeys = true }

    @Test fun parses_opportunities_with_new_fields() {
        val txt = javaClass.classLoader!!.getResource("quant_report_sample.json")!!.readText()
        val dto = json.decodeFromString<QuantReportDto>(txt)
        val o = dto.opportunities.first()
        assertEquals("Red Sox −1.5", o.title)
        assertEquals(0.30, o.curPrice!!, 1e-6)
        assertTrue(o.expectedValue!! > 0)
        assertEquals("model", o.qSource)
        assertNotNull(o.winProbEst)
        assertEquals(true, o.betEligible)
    }
}
