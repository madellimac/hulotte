#include "Packer.hpp"

using namespace spu;
using namespace spu::module;

Packer::Packer(int frame_size, int packing_ratio, int data_width)
    : Stateful(), frame_size(frame_size), packing_ratio(packing_ratio), data_width(data_width)
{

    mask = (1 << data_width) - 1;
    if (data_width*packing_ratio > 32)
    {
        std::stringstream message;
        message << "cannot pack " << packing_ratio << "data of width " << data_width << " in a 32 bits word";
        throw tools::invalid_argument(__FILE__, __LINE__, __func__, message.str());
    }

    this->set_name("Packer");
    this->set_short_name("Packer");
    
    auto &t = create_task("pack");
    auto input   = create_socket_in<int>(t, "input", frame_size*packing_ratio);
    auto output   = create_socket_out<int>(t, "output", frame_size);
    this->create_codelet(t, [input, output](Module &m, runtime::Task &t, const size_t frame_id) -> int {
        static_cast<Packer&>(m).pack(   static_cast<int*>(t[input].get_dataptr()),
                                                static_cast<int*>(t[output].get_dataptr()),
                                                        frame_id);
        return 0;
    });

}

void Packer::pack(int* input, int* output, const int frame_id)
{
    for (auto i = 0; i < frame_size; i++)
    {
        output[i] = 0;
        for (auto j = 0; j < packing_ratio; j++)
            output[i] = ((mask&input[packing_ratio*i + j]) << (j*data_width)) | output[i];
    }
}