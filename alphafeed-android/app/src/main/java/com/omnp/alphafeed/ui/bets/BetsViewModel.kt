package com.omnp.alphafeed.ui.bets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.omnp.alphafeed.data.BoardResult
import com.omnp.alphafeed.domain.BoardGating
import com.omnp.alphafeed.domain.Row
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface BetsUi {
    data object Loading : BetsUi
    data class Content(val rows: List<Row>, val isOffline: Boolean, val updatedAt: String?) : BetsUi
    data class Error(val message: String) : BetsUi
}

class BetsViewModel(
    private val loader: suspend () -> BoardResult,
    private val isProFlow: StateFlow<Boolean>
) : ViewModel() {
    private val _state = MutableStateFlow<BetsUi>(BetsUi.Loading)
    val state: StateFlow<BetsUi> = _state.asStateFlow()

    init {
        load()
    }

    fun retry() {
        load()
    }

    private fun load() {
        _state.value = BetsUi.Loading
        viewModelScope.launch {
            try {
                val res = loader()
                _state.value = BetsUi.Content(
                    rows = BoardGating.rows(res.bets, isProFlow.value),
                    isOffline = res.isOffline,
                    updatedAt = res.updatedAt
                )
            } catch (e: Exception) {
                _state.value = BetsUi.Error(e.message ?: "error")
            }
        }
    }
}
