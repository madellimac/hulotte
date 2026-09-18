#include "custom/CustomModule.hpp"

#include <algorithm>

CustomModule::CustomModule(int frame_size)
: spu::module::Stateful(), frame_size(frame_size)
{
    this->set_name("CustomModule");
    this->set_short_name("CustomModule");

    auto& task = this->create_task("process");
    auto input = this->create_socket_in<int>(task, "in", frame_size);
    auto output = this->create_socket_out<int>(task, "out", frame_size);

    this->create_codelet(task, [input, output](spu::module::Module& module,
                                                spu::runtime::Task& task,
                                                const size_t) -> int {
        auto& custom = static_cast<CustomModule&>(module);
        custom.process(static_cast<int*>(task[input].get_dataptr()),
                       static_cast<int*>(task[output].get_dataptr()));
        return spu::runtime::status_t::SUCCESS;
    });
}

CustomModule* CustomModule::clone() const
{
    auto cloned = new CustomModule(*this);
    cloned->deep_copy(*this);
    return cloned;
}

void CustomModule::process(const int* input, int* output)
{
    std::copy(input, input + frame_size, output);
}
