//! Headless wgpu instance, adapter and device.

use vello::wgpu;

/// Why the GPU backend could not start; callers fall back to the CPU backend.
#[derive(Debug)]
pub enum GpuBackendError {
    NoAdapter(String),
    DeviceRequestFailed(String),
    RendererCreationFailed(String),
}

impl std::fmt::Display for GpuBackendError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            GpuBackendError::NoAdapter(e) => write!(f, "no GPU adapter available: {e}"),
            GpuBackendError::DeviceRequestFailed(e) => write!(f, "GPU device request failed: {e}"),
            GpuBackendError::RendererCreationFailed(e) => write!(f, "Vello renderer creation failed: {e}"),
        }
    }
}

impl std::error::Error for GpuBackendError {}

pub(crate) struct GpuContext {
    pub device: wgpu::Device,
    pub queue: wgpu::Queue,
    pub adapter_description: String,
}

impl GpuContext {
    /// Picks the default (high-performance) adapter, honoring `WGPU_BACKEND` and
    /// `WGPU_ADAPTER_NAME`. Software adapters (e.g. llvmpipe) are accepted.
    pub fn new() -> Result<Self, GpuBackendError> {
        let mut descriptor = wgpu::InstanceDescriptor::new_without_display_handle();
        descriptor.backends = wgpu::Backends::from_env().unwrap_or_default();
        descriptor.flags = wgpu::InstanceFlags::from_build_config().with_env();
        let instance = wgpu::Instance::new(descriptor);
        let adapter = pollster::block_on(wgpu::util::initialize_adapter_from_env_or_default(&instance, None))
            .map_err(|e| GpuBackendError::NoAdapter(e.to_string()))?;
        let info = adapter.get_info();
        let adapter_description = format!("{} ({:?})", info.name, info.backend);
        let optional_features = wgpu::Features::CLEAR_TEXTURE | wgpu::Features::PIPELINE_CACHE;
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            label: Some("kinemo-render-gpu"),
            required_features: adapter.features() & optional_features,
            required_limits: wgpu::Limits::default().using_resolution(adapter.limits()),
            ..Default::default()
        }))
        .map_err(|e| GpuBackendError::DeviceRequestFailed(e.to_string()))?;
        Ok(GpuContext { device, queue, adapter_description })
    }
}
